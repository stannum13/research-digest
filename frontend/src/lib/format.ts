export function formatDigestDate(date = new Date()): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}

export function formatArchiveDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(dateFromIsoDate(value));
}

export function formatShortDate(value: string | null | undefined): string {
  if (!value) {
    return "not yet";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function formatTimeAgo(value: string | null | undefined): string {
  if (!value) {
    return "not yet";
  }

  const date = new Date(value);
  const diff = Date.now() - date.getTime();
  const minutes = Math.max(1, Math.round(diff / 60000));

  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "not yet";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function toIsoDate(date = new Date()): string {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function dateFromIsoDate(value: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);

  if (!match) {
    return new Date(value);
  }

  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function addIsoDateDays(value: string, days: number): string {
  const date = dateFromIsoDate(value);
  date.setDate(date.getDate() + days);
  return toIsoDate(date);
}

export function isWithinLastDays(value: string, days: number): boolean {
  const date = new Date(value);
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return date.getTime() >= cutoff;
}

export function sentenceList(items: string[], limit = 3): string {
  const visible = items.slice(0, limit);
  const suffix = items.length > limit ? ` +${items.length - limit}` : "";
  return `${visible.join(", ")}${suffix}`;
}
