/// <reference types="vite/client" />

interface ImportMetaEnv {
	/** Backend origin, e.g. https://your-service.up.railway.app (no trailing slash). */
	readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
