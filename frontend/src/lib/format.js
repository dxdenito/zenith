export function money(value, currency = "USD") {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (Number.isNaN(number)) return "—";
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(number);
  } catch {
    return `${number.toFixed(2)} ${currency}`;
  }
}