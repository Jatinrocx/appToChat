# Chat App Backend

A real-time chat application backend built with **Python + FastAPI + WebSockets**, featuring group chat, role-based access control (RBAC), typing indicators, and file message relay.

## Live Demo

- **API Docs (Swagger):** `http://localhost:8000/docs`
- **Chat Interface:** `http://localhost:8000/chat`

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd chat-app-backend

# 2. Create virtual environment
python -m venv venv

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
python -m uvicorn app.main:app --reload --port 8000

# 5. Open http://localhost:8000/chat in your browser
```

---

## System Architecture

```
                          ┌─────────────────────────────────┐
                          │        FastAPI Server            │
  Clients                 │                                 │
  ┌──────┐   WebSocket    │  ┌──────────────────────────┐   │
  │User A├───────────────►│  │  WebSocket Handler       │   │
  └──────┘                │  │  - Message routing        │   │
                          │  │  - Typing broadcast       │   │      ┌─────────┐
  ┌──────┐   WebSocket    │  │  - Online/offline track   │   ├─────►│ SQLite / │
  │User B├───────────────►│  └──────────┬───────────────┘   │      │PostgreSQL│
  └──────┘                │             │                   │      └─────────┘
                          │  ┌──────────▼───────────────┐   │
  ┌──────┐   HTTP/REST    │  │  Connection Manager      │   │
  │User C├───────────────►│  │  - Tracks connections     │   │
  └──────┘                │  │  - Group-based rooms      │   │
                          │  │  - Broadcast to members   │   │
                          │  └──────────────────────────┘   │
                          │                                 │
                          │  ┌──────────────────────────┐   │
                          │  │  REST API Endpoints       │   │
                          │  │  - Auth (register/login)  │   │
                          │  │  - Groups (CRUD + RBAC)   │   │
                          │  │  - Messages (upload/hist) │   │
                          │  └──────────────────────────┘   │
                          └─────────────────────────────────┘
```

---

## Architecture Answers

### 1. What are you using for implementing WebSockets?

**FastAPI's native WebSocket support**, built on top of Starlette and the `websockets` Python library.

**Why FastAPI?**
- **Async-first:** Uses Python's `asyncio` for non-blocking I/O, efficiently handling thousands of concurrent WebSocket connections.
- **Built-in WebSocket support:** No additional library needed — Starlette provides `WebSocket` class with `accept()`, `send_json()`, `receive_json()` methods.
- **Integrated auth:** WebSocket connections are authenticated using JWT tokens passed as query parameters, verified using the same auth middleware as REST endpoints.

**Connection Management Architecture:**
- A singleton `ConnectionManager` class tracks all active connections in a dictionary: `{group_id: {user_id: WebSocket}}`.
- On connect: verifies JWT token, checks group membership and role, registers the connection.
- On disconnect: removes from active connections, broadcasts "user left" to group.
- Broadcasting: iterates over all connections in a group and sends the message via `send_json()`.

```python
# WebSocket endpoint
@router.websocket("/ws/{group_id}")
async def websocket_endpoint(websocket: WebSocket, group_id: int):
    token = websocket.query_params.get("token")
    user = verify_jwt(token)
    await manager.connect(websocket, user.id, group_id)
    # ... listen for messages
```

### 2. How would you support other message types like audio, documents, etc?

**Using a hybrid REST + WebSocket approach with a relay model:**

1. **File Upload (REST):** Client uploads the file via `POST /messages/upload` with multipart form data. The server:
   - Validates file type against an allowlist (images, audio, documents)
   - Validates file size (max 10MB)
   - Temporarily stores the file on the server
   - Saves **metadata only** to the database (filename, size, type, sender, timestamp)

2. **Notification (WebSocket):** After upload, a message notification is broadcast to all group members via WebSocket, containing only metadata.

3. **Download (REST):** Recipients download the file via `GET /uploads/{type}/{filename}`. The file is served as a static file.

**Database stores metadata only (relay model):**
```
| sender | type     | file_name    | file_size | timestamp   |
|--------|----------|------------- |-----------|-------------|
| user_1 | audio    | meeting.mp3  | 2.1MB     | 2024-03-29  |
| user_2 | document | report.pdf   | 450KB     | 2024-03-29  |
```

The server acts as a **relay** — it doesn't permanently store file contents. This reduces storage costs and improves privacy (similar to Signal's approach).

**Supported types:**
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- Audio: `.mp3`, `.wav`, `.ogg`, `.m4a`
- Documents: `.pdf`, `.doc`, `.docx`, `.txt`, `.xlsx`, `.csv`

### 3. How do we check if someone is typing?

**Using ephemeral WebSocket events:**

When a user starts typing, the client sends a `typing_start` event. When they stop (2-second debounce), a `typing_stop` event is sent. The server broadcasts these to all other members in the group.

**Client-side flow:**
```javascript
// On every keystroke
function handleTyping() {
    if (!isTyping) {
        ws.send(JSON.stringify({type: 'typing_start'}));
        isTyping = true;
    }
    // Reset the 2-second timer
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        ws.send(JSON.stringify({type: 'typing_stop'}));
        isTyping = false;
    }, 2000);
}
```

**Server-side flow:**
```python
# On receiving typing event
if msg_type == "typing_start":
    manager.set_typing(user_id, group_id, True)
    await manager.broadcast_to_group(group_id, {
        "type": "typing",
        "user_id": user_id,
        "username": username,
        "is_typing": True,
    }, exclude_user_id=user_id)  # Don't send back to the typer
```

**Key design decisions:**
- **Ephemeral:** Typing events are **NOT** saved to the database — they're transient, real-time only.
- **Debounced:** 2-second inactivity timeout prevents excessive events.
- **Excluded sender:** The typing indicator is broadcast to everyone except the person typing.
- **Auto-cleared:** When a message is sent, the typing state is automatically cleared.
- **Tracked in memory:** The `ConnectionManager` maintains a `typing_users: {group_id: Set[user_id]}` for each group.

### 4. How can we separate the Admin, Read, or Write members in the group?

**Using Role-Based Access Control (RBAC) via a `group_members` join table:**

```
group_members table:
| user_id | group_id | role   |
|---------|----------|--------|
| 1       | 1        | admin  |
| 2       | 1        | write  |
| 3       | 1        | read   |
```

**Three roles with clear permissions:**

| Action | Admin | Write | Read |
|--------|-------|-------|------|
| View messages | Yes | Yes | Yes |
| Send text messages | Yes | Yes | No |
| Upload files | Yes | Yes | No |
| Add members | Yes | No | No |
| Remove members | Yes | No | No |
| Change roles | Yes | No | No |
| Delete group | Yes | No | No |

**Enforcement happens at two levels:**

1. **REST API level:** Before any state-changing operation, the server checks the user's role in the group:
```python
def require_admin(db, group_id, user_id):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id,
    ).first()
    if not member or member.role != "admin":
        raise HTTPException(status_code=403)
```

2. **WebSocket level:** Before broadcasting a message from a user, the server checks their role:
```python
if role == "read":
    await manager.send_to_user(user_id, group_id, {
        "type": "error",
        "message": "You have read-only access in this group"
    })
    return  # Message is NOT broadcast
```

**Why a join table instead of a role on the User model?**
Because a user can have **different roles in different groups** — admin in "Project Alpha" but read-only in "Company Announcements".

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | FastAPI | Async web framework with native WebSocket support |
| Server | Uvicorn | ASGI server for running FastAPI |
| Database | SQLite (dev) / PostgreSQL (prod) | Persistent storage |
| ORM | SQLAlchemy | Database abstraction layer |
| Auth | JWT (PyJWT) | Stateless authentication |
| Password Hashing | bcrypt (passlib) | Secure password storage |
| File Upload | python-multipart | Multipart form data handling |

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create new account |
| POST | `/auth/login` | Login, get JWT token |
| GET | `/auth/me` | Get current user info |

### Groups
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/groups` | Create a new group |
| GET | `/groups/me` | List my groups |
| GET | `/groups/{id}` | Get group details + members |
| POST | `/groups/{id}/members` | Add member (admin only) |
| PUT | `/groups/{id}/members/{uid}/role` | Change role (admin only) |
| DELETE | `/groups/{id}/members/{uid}` | Remove member (admin only) |

### Messages
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/messages/upload` | Upload file to group |
| GET | `/messages/{group_id}/history` | Get message history (paginated) |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/{group_id}?token=JWT` | Real-time chat connection |

## Project Structure

```
chat-app-backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py             # Settings & configuration
│   ├── database.py           # SQLAlchemy setup
│   ├── auth/
│   │   └── jwt_handler.py    # JWT token management
│   ├── models/
│   │   ├── user.py           # User model
│   │   ├── group.py          # Group + GroupMember (RBAC)
│   │   └── message.py        # Message model (multi-type)
│   ├── schemas/
│   │   ├── user.py           # Request/response schemas
│   │   ├── group.py
│   │   └── message.py
│   ├── routers/
│   │   ├── auth.py           # Register, Login
│   │   ├── groups.py         # Group CRUD + RBAC
│   │   └── messages.py       # File upload + history
│   └── websocket/
│       ├── manager.py        # Connection tracking
│       └── handler.py        # WebSocket endpoint
├── static/
│   └── index.html            # Chat test interface
├── requirements.txt
└── README.md
```
