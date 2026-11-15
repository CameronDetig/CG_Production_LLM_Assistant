# HTTP API

The backend API that the web frontend and the Blender add-on both call. It is implemented in `backend/api_app.py` (FastAPI) and served at `/api/*` on the site's CloudFront domain, which forwards to the Lambda function's Function URL. CloudFront signs those requests (origin access control), so the Function URL rejects anything that does not come through CloudFront.

A machine-readable schema is in [openapi.json](openapi.json). Paste it into any OpenAPI viewer (for example <https://editor.swagger.io>) to browse it as Swagger. It is generated, so regenerate it rather than editing it (see [Regenerating the OpenAPI file](#regenerating-the-openapi-file)). The interactive Swagger page is deliberately not served by the live site.

OpenAPI cannot describe the event stream that `/api/chat` returns, so that part is documented only here.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | No | Liveness check |
| POST | `/api/auth` | No | Exchange an email and password for Cognito tokens |
| POST | `/api/signup` | No | Create an account |
| POST | `/api/warmup` | Yes | Pre-load models and database pools |
| POST | `/api/warmup/stream` | Yes | The same warm-up, plus a database wake on every call, reporting progress as a Server-Sent Events stream |
| GET | `/api/filters` | Yes | List the shows and file types a search can be limited to |
| POST | `/api/chat` | Yes | Ask a question; returns a Server-Sent Events stream |
| GET | `/api/conversations` | Yes | List the caller's conversations |
| GET | `/api/conversations/{conversation_id}` | Yes | Get one conversation with its messages |
| DELETE | `/api/conversations/{conversation_id}` | Yes | Delete a conversation |

## Authentication

Authenticated endpoints need a Cognito **ID token**. Requests through CloudFront need two headers:

```
X-Cognito-Token: <id_token>
X-Amz-Content-Sha256: <hex SHA-256 of the request body>
```

CloudFront replaces `Authorization` with its own signature when it forwards the request to Lambda, so the token has to travel in `X-Cognito-Token`. That signature also covers the body, which is why every request, including ones without a body or without a token such as `POST /api/auth`, must send the body hash (the hash of an empty string for no body). The backend validates the token itself on every protected route. When calling a local backend directly, `Authorization: Bearer <id_token>` also works. The web frontend (`frontend_web/src/api.ts`) and the Blender add-on (`frontend_blender/api_client.py`) send all three.

The web frontend gets its token from the Cognito hosted sign-in page. Clients that cannot do a browser redirect, such as the Blender add-on, use `POST /api/auth`.

A missing or invalid token returns `401`.

## Errors

Errors raised by the backend are JSON with a `detail` field:

```json
{ "detail": "Conversation not found" }
```

A request body that fails validation returns `422`, where `detail` is a list describing each invalid field. A request that CloudFront cannot sign correctly, for example a `POST` without `X-Amz-Content-Sha256`, is rejected by Lambda with `403` before it reaches the backend.

Failures inside a chat stream are reported as an `error` event in the stream, not as an HTTP status (see below).

## POST /api/auth and POST /api/signup

Request for both:

```json
{ "email": "artist@example.com", "password": "..." }
```

`/api/auth` response (`401` if the credentials are wrong):

```json
{ "id_token": "...", "access_token": "...", "refresh_token": "...", "user_id": "artist@example.com" }
```

`/api/signup` response (`400` with a `detail` message if sign-up fails). The token fields and `user_id` are present only when the account is confirmed immediately:

```json
{ "message": "...", "user_confirmed": false }
```

## POST /api/warmup

No body. Loads the agent stack, the text embedding model and the database pools so the first chat request is not a cold one. It is best effort; clients should ignore failures.

```json
{ "status": "warm" }
```

On the first call in a container the response also has a `steps` object with each step's duration or `"failed"`, and `status` is `"partial"` if any step failed.

This route does nothing once its container is warm, so it does not wake a database that paused afterwards. Clients that show progress or want the database awake should use the stream below.

## POST /api/warmup/stream

No body. Loads the models once per container and, on every call, waits for the metadata database to answer. The database pauses after five idle minutes and takes about 15 seconds to resume, so both clients call this after sign-in and again when the user returns after a quiet period, instead of leaving that wait to the first question.

The response is a Server-Sent Events stream of `status` events with the same `stage` and `message` fields the chat stream uses. Show `message` to people.

| `stage` | `message` | Meaning |
|---|---|---|
| `server_ready` | Server is up | The backend is running. Until this arrives a client can assume it is still starting. |
| `warming` | Waking the database and loading models, Waking the database, or Loading models | What is still in progress. Sent again each time one part finishes. |
| `ready` | Ready | Everything answered. `steps` has the time each part took, or `"warm"` for models already loaded. |
| `partial` | The database is not responding yet, or The assistant is not fully loaded yet | Something failed. It is retried on the next call; chat requests can still be sent. |

```text
event: status
data: {"stage": "server_ready", "message": "Server is up"}

event: status
data: {"stage": "warming", "message": "Waking the database and loading models"}

event: status
data: {"stage": "warming", "message": "Waking the database"}

event: status
data: {"stage": "ready", "message": "Ready", "steps": {"models": "4210ms", "database": "14870ms"}}
```

Warm-up is best effort: clients should ignore failures. Each backend instance serves one request at a time, so a chat request sent while this stream is open starts a second, cold instance. Both clients hold a question submitted during warm-up until the stream ends (for at most 30 seconds) and tell the user the assistant is still starting up.

## GET /api/filters

Returns the values the search filters can take, with the number of files for each. Clients use it to build their filter checkboxes.

```json
{
  "shows": [
    { "name": "charge", "file_count": 3159 },
    { "name": "spring", "file_count": 8042 }
  ],
  "file_types": [
    { "name": "blend", "file_count": 2861 },
    { "name": "image", "file_count": 13705 }
  ]
}
```

- `shows[].name` is a value of `files.show`. `other` holds files that belong to no show.
- `file_types[].name` is a value of `files.file_type` (`image`, `video`, `blend`, and so on).
- Both lists are sorted by name. The result is cached in each backend container for 10 minutes, so newly scanned files can take that long to appear.

## POST /api/chat

Request:

```json
{
  "query": "Find close-up character renders",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "uploaded_image_base64": "<base64 JPEG>",
  "filters": {
    "shows": ["spring", "charge"],
    "file_types": ["image"]
  }
}
```

| Field | Required | Notes |
|---|---|---|
| `query` | Yes | 1 to 20,000 characters |
| `conversation_id` | No | Continue an existing conversation. Omitted, or unknown to this user, starts a new one. |
| `uploaded_image_base64` | No | Reference image for visual similarity search, at most 2,000,000 characters. The clients send a 512x512 JPEG. |
| `filters` | No | Limit the search. See below. |

### Search filters

`filters.shows` and `filters.file_types` each take up to 100 strings of 1 to 255 characters, using the names from `GET /api/filters`.

- Values inside one list are alternatives: `"shows": ["spring", "charge"]` searches files from either show.
- The two lists combine: with both set, a file must match one of the shows **and** one of the file types.
- An empty or omitted list does not limit that dimension. Omitting `filters` searches everything, which is what clients that predate filters do.
- A value that matches nothing is not an error; the search just finds no rows for it.

Filters are enforced by the backend, not left to the language model. Before a generated SQL query runs, the backend puts CTEs in front of it that are named after the real tables (`files`, each per-type table such as `images`, `videos` and `blend_files`, and `shows`) and contain only the rows inside the selection. PostgreSQL resolves a table name to a CTE of that name first, so the whole query sees only those rows (`backend/src/services/search_filters.py`). A question about a show outside the selection therefore finds nothing, even if the question names that show.

The model's SQL text itself is left untouched. While filters are active, a generated query is refused and retried if it would sidestep the CTEs: a schema-qualified table such as `public.files`, a CTE named after one of those tables, or `WITH RECURSIVE`.

The SQL reported in `sql_query` events is the query as the model wrote it, without the filter CTEs. The `filters` event is the record of what restriction was applied.

Filters apply to one request. They are not remembered for the conversation, so send them with every message they should apply to.

### Response: event stream

The response is `text/event-stream`. Each event is an `event:` line, a `data:` line holding one JSON object, and a blank line. Lines starting with `:` are heartbeat comments and carry no data.

Events are sent as each step finishes, both locally and when deployed (the Function URL uses `RESPONSE_STREAM` and the adapter runs with `AWS_LWA_INVOKE_MODE=response_stream` in `backend/Dockerfile`). Clients should show them as they arrive. The interpreted request, SQL and results come from inside the agent while it runs, so they appear before the answer starts.

Events, in the order they are sent:

| Event | Data | When |
|---|---|---|
| `agent_start` | `conversation_id`, `attempts` | Always first. Use `conversation_id` for the next message. |
| `filters` | `shows`, `file_types` | Only when the request had at least one filter value |
| `status` | `stage`, `message` | Progress text for display. Sent whenever the assistant moves to a new step (see the stages below), so it can appear several times and between the other events. |
| `enhanced_query` | `query` | The request as the assistant interpreted it. Absent for general questions that need no database query. |
| `sql_query` | `query`, `attempt` | Once per SQL attempt |
| `query_results` | `count`, `attempt`, `results` | After an attempt that ran. `results` holds at most the first 5 rows. |
| `retry_feedback` | `feedback`, `attempt` | After an attempt judged unsatisfactory. A second `sql_query` with `attempt: 2` follows. |
| `thumbnail` | `file_id`, `file_name`, `file_type`, `thumbnail_url` | Once per result with a thumbnail, at most 10. `thumbnail_url` is a presigned URL that expires. |
| `answer_start` | (empty) | The answer text follows |
| `answer_chunk` | `text` | One or more; concatenate `text` to build the answer |
| `answer_end` | (empty) | |
| `done` | `conversation_id`, `message_count` | Always last on success |

`status` stages, in the order they can occur. Show `message` to people; use `stage` in code.

| `stage` | `message` |
|---|---|
| `waking_database` | Waking the database (about 15 seconds). Only sent when the database had paused and the request has to wait for it to resume. |
| `analyzing` | Analyzing your request |
| `embedding` | Preparing similarity search, or Encoding your uploaded image (only for similarity and image searches) |
| `generating_sql` | Writing a database query, or Revising the database query (attempt N) |
| `running_sql` | Running the query |
| `evaluating` | Checking the results |
| `answering` | Writing the answer |

General questions that need no database query go straight from `analyzing` to `answering`. New stages may be added; treat an unknown `stage` like any other and show its `message`.

If the request fails after the stream has started, the stream ends with `error` (`message`) followed by `done` with `"failed": true`.

Clients must ignore event types they do not recognise, so that new events can be added.

Rows in `query_results` are whatever columns the generated SQL selected, plus `thumbnail_url` and `download_url` (a presigned link for `.blend` files, otherwise `null`).

Example stream for a filtered request:

```
event: agent_start
data: {"conversation_id": "550e8400-e29b-41d4-a716-446655440000", "attempts": 0}

event: filters
data: {"shows": ["spring"], "file_types": ["image"]}

event: status
data: {"stage": "analyzing", "message": "Analyzing your request"}

event: enhanced_query
data: {"query": "Count the image files"}

event: status
data: {"stage": "generating_sql", "message": "Writing a database query"}

event: sql_query
data: {"query": "SELECT COUNT(*) FROM files f WHERE f.file_type = 'image'", "attempt": 1}

event: status
data: {"stage": "running_sql", "message": "Running the query"}

event: query_results
data: {"count": 1, "attempt": 1, "results": [{"count": 214, "thumbnail_url": null, "download_url": null}]}

event: status
data: {"stage": "evaluating", "message": "Checking the results"}

event: status
data: {"stage": "answering", "message": "Writing the answer"}

event: answer_start
data: {}

event: answer_chunk
data: {"text": "There are 214 images in Spring."}

event: answer_end
data: {}

event: done
data: {"conversation_id": "550e8400-e29b-41d4-a716-446655440000", "message_count": 2}
```

## Conversations

`GET /api/conversations` returns up to 50 conversations:

```json
{
  "conversations": [
    {
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Close-up character renders",
      "created_at": "2026-11-11T09:00:00Z",
      "updated_at": "2026-11-11T09:02:13Z",
      "message_count": 4
    }
  ]
}
```

`GET /api/conversations/{conversation_id}` returns `{"conversation": {...}}` with the same fields plus `messages`. Each message has `role` (`user` or `assistant`), `content` and `timestamp`. Assistant messages also have `tool_calls`, a one-item list recording the final `sql_query`, the `result_count`, up to 10 `results` rows, and the `filters` that were applied (present only when the request was filtered).

`DELETE /api/conversations/{conversation_id}` returns `{"message": "Conversation deleted"}`.

Both return `404` when the conversation does not exist or belongs to another user.

## Changing the API

- Add request and response fields as optional, and keep ignoring unknown SSE events in the clients, so the web frontend and the Blender add-on can be released independently of the backend.
- Update this file and regenerate `openapi.json` in the same commit as the change.
- New `/api/*` paths need no infrastructure change: CloudFront sends every `/api/*` request to the Function URL. Protect an authenticated path with the `authenticated_user` dependency in `backend/api_app.py`; nothing in front of the backend checks tokens.

### Regenerating the OpenAPI file

From the repository root, in an environment with `fastapi`, `boto3` and `python-jose` installed:

```sh
python backend/scripts/export_openapi.py
```

The script only reads the route definitions; it needs no AWS access.
