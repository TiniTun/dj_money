// Kept in its own module so tests can mock it.
export function redirectToLogin(): void {
  window.location.assign('/accounts/login/?next=/')
}
