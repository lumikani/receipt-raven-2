/** A card's last four digits, masked: •••• 1234. */
export function MaskedCard({ digits }: { digits: string }) {
  return <>•••• {digits}</>;
}
