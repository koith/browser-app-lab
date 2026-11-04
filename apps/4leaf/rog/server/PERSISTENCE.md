# 4LEAF encrypted durable chat snapshots (opt-in)

GitHub Pages talks only to the existing central Node HTTPS service. The
browser receives no Supabase URL, secret API key, or encryption key.

The free Render Node service has no permanent disk. Code deployment alone
does not make the current live chat durable. First provision a selected,
dedicated database and apply the SQL file in this directory.

Set these variables only on the secure Node service, never in Pages:

- LEAF_CENTRAL_DB_URL : HTTPS project URL for the selected dedicated Supabase project
- LEAF_CENTRAL_DB_SECRET : backend-only service-role or secret API key
- LEAF_CENTRAL_ARCHIVE_KEY : exactly 64 hex characters from 32 random bytes
- LEAF_CENTRAL_DB_SLOT : optional archive identity (default production)

Keep a separate encrypted offline copy of the archive key. Losing it makes
stored chat history irrecoverable. The AES-256-GCM encrypted gzip payload
has a SHA-256 integrity checksum and optimistic revision lock.

At startup, remote state MUST be read and authenticated before requests
are served. A missing/bad key, unavailable database, corrupt archive, or
revision conflict fails closed with HTTP 503 and never resets the archive.
A structurally malformed room, orphaned history, repeated room ID, inconsistent
message sequence, or history exceeding the 200-entry retention limit makes the
entire archive fail closed: the server does not silently filter records and
later erase the rejected subset. A lost optimistic revision race also sets
`/api/health` to HTTP 503 until the server restarts against the authoritative
archive. Both conditions need operator recovery, not an empty-state reset.

Room create/close, ownership transfer and each chat message wait for a
successful remote commit before sending HTTP success. Errors roll back
the in-process mutation.

Public ChatRoom participant recovery: when the Node service restarts, its
in-memory guest sessions disappear. A guest who committed a chat message may
recover their original sender ID using their existing 256-bit bearer token and
the SHA-256 token fingerprint preserved **inside the encrypted archive**.
This allows a lost HTTP chat acknowledgement to be retried with the original
`clientMessageId` exactly once. Both the ID and token fingerprint are
stripped from public messages and other participants' snapshots. A different
sender who reuses the same message ID receives HTTP 409, even with identical
text; an unknown resume token never claims an archived participant identity.

This is **not** permanent account login: a guest with no retained archived
messages and no owned room may receive a new ID after restart, and histories
are intentionally limited to 200 retained messages per room. Legacy encrypted
archives without message sender fingerprints remain readable, but cannot
retroactively prove a public guest's identity. Backend-only keys and ciphertext
remain necessary; this does not make ephemeral Render storage durable.

The old LEAF_CENTRAL_STORAGE local file remains available for isolated
tests or hosting with an actually persistent mounted volume.
Like remote archives, **local JSON files now undergo complete structural
validation before the service starts**. Invalid JSON, malformed rooms,
orphaned or oversized history, and duplicate IDs make startup fail without
rewriting, dropping, or silently truncating any original data. Preserve the
corrupt original for recovery; never replace it with a blank archive.
Local writes use a same-directory temporary file and atomic rename; this is
not a substitute for a persistent disk, an off-site backup, or crash-proof
power-loss guarantees. The free
Render instance's local directory is not a durable substitute.

Free Supabase may pause after inactivity and provides no automatic
downloadable backup. Therefore database-backed durability is NOT a
guarantee of uninterrupted service. Production acceptance requires a
selected isolated project, real service credentials, restart+re-read
evidence, and a second restore check. No schema DDL or billing is
triggered merely by committing this implementation.
