interface ImportMetaEnv {
  readonly BASE_URL: string
  readonly MODE: string
  readonly DEV: boolean
  readonly PROD: boolean
  readonly SSR: boolean
  readonly VITE_WORKWINGS_API_TARGET?: string
  readonly VITE_WORKWINGS_ACTOR_ID?: string
  readonly VITE_WORKWINGS_ACTOR_ROLES?: string
  readonly VITE_ADMIN_USERNAMES?: string
  readonly VITE_POLLINATIONS_KEY?: string
  readonly VITE_ENABLE_LOCAL_TEST_LOGIN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
