/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/react" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DATA_MODE?: "api" | "demo";
  readonly VITE_INSTITUTION_NAME?: string;
  readonly VITE_PRIVACY_CONTACT?: string;
  readonly VITE_SUPPORT_CONTACT?: string;
  readonly VITE_MAP_URL?: string;
  readonly VITE_LIVESTREAM_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
