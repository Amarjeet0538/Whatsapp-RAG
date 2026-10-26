// API timestamps are ISO strings with the chat's offset (+05:30). Show them in that
// zone, not the viewer's, so times match what the chat itself says.
const TZ = "Asia/Kolkata";

const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", timeZone: TZ });
const timeFmt = new Intl.DateTimeFormat("en-IN", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: TZ,
});

export const fmtDate = (iso: string) => dateFmt.format(new Date(iso));
export const fmtTime = (iso: string) => timeFmt.format(new Date(iso));
export const fmtDateTime = (iso: string) => `${fmtDate(iso)}, ${fmtTime(iso)}`;

export function fmtRange(startIso: string, endIso: string): string {
  const sameDay = fmtDate(startIso) === fmtDate(endIso);
  return sameDay
    ? `${fmtDate(startIso)}, ${fmtTime(startIso)} to ${fmtTime(endIso)}`
    : `${fmtDateTime(startIso)} to ${fmtDateTime(endIso)}`;
}

export const fmtScore = (n: number) => n.toFixed(2);
