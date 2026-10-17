# Privacy and data handling

Files are stored locally under `MEDNLP_STORAGE_DIR`, outside the frontend public directory, and deleted with their document record. A random object key avoids trusting uploaded paths. Application logs contain processing IDs and generic error categories, not report text. No external LLM or analytics provider is configured. Set an explicit storage location, protect the host, set a strong secret before deployment, and configure deletion/backup policy yourself.

The API supports username/password registration and login, PBKDF2 password hashing, expiring signed bearer tokens, and per-user document ownership checks. The frontend stores the token in local storage; deployments exposed to hostile origins should adopt a stronger session design and review XSS protections. Retention configuration is exposed but automated expiry is not implemented. Do not upload identifiable health information.
