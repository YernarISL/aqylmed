/** The backend stores UTC timestamps without a timezone suffix — treat them as UTC, show in local time. */
export const formatDate = (iso: string): string =>
  new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleString();
