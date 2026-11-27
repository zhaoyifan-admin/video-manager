import 'axios'

declare module 'axios' {
  interface AxiosRequestConfig {
    _skipAuthRedirect?: boolean
  }

  interface InternalAxiosRequestConfig {
    _skipAuthRedirect?: boolean
  }
}
