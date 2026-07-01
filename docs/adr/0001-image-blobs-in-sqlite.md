# Images stored as blobs in SQLite

We chose to store images as binary blobs in SQLite alongside post records rather than on the filesystem or in object storage. The user wanted single-file portability: the SQLite database is the entire application state — posts, images, analytics, comments, everything. Backing up the blog is copying one file. The cost is that SQLite blob serving is slower than filesystem reads and the database grows with binary data, but at the scale of a single-author blog (hundreds of posts, not millions) this is negligible.

**Considered Options**: filesystem storage (rejected: breaks single-file backup), S3/Cloudinary (rejected: external dependency, overkill for a personal blog).
