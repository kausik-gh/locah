/**
 * ESC/POS receipts for 58 / 80 mm thermal printers (Capability Universe §14.1,
 * hardware row: "ESC/POS printers; drawer kick via printer"). Plain text with
 * the standard commands: initialise, bold, cut, and the drawer-kick pulse.
 * Sent over Web Serial where the browser has it, so no printer driver is
 * needed; otherwise the counter prints the receipt page through the browser.
 * Built to the common ESC/POS command set; to be checked on the pilot's
 * printers before rollout.
 */

const ESC = 0x1b
const GS = 0x1d

export type ReceiptText = { width: 32 | 48; lines: { text: string; bold?: boolean; center?: boolean }[] }

export function receiptBytes(r: ReceiptText, { cut = true, kick = false } = {}): Uint8Array {
  const out: number[] = [ESC, 0x40] // initialise
  const enc = new TextEncoder()
  for (const l of r.lines) {
    out.push(ESC, 0x61, l.center ? 1 : 0) // align
    out.push(ESC, 0x45, l.bold ? 1 : 0) // bold
    // Thermal printers' default code page has no ₹; print "Rs." instead.
    out.push(...enc.encode(l.text.replace(/₹/g, 'Rs.').slice(0, r.width)), 0x0a)
  }
  out.push(0x0a, 0x0a, 0x0a)
  if (kick) out.push(ESC, 0x70, 0x00, 0x19, 0xfa) // pulse drawer pin 2
  if (cut) out.push(GS, 0x56, 0x42, 0x00) // feed and partial cut
  return new Uint8Array(out)
}

type SerialPortLike = { open: (o: { baudRate: number }) => Promise<void>; writable: WritableStream<Uint8Array>; close: () => Promise<void> }
type SerialLike = { requestPort: () => Promise<SerialPortLike> }

export function canPrintDirect(): boolean {
  return typeof navigator !== 'undefined' && 'serial' in navigator
}

export async function printDirect(bytes: Uint8Array): Promise<void> {
  const serial = (navigator as unknown as { serial: SerialLike }).serial
  const port = await serial.requestPort()
  await port.open({ baudRate: 9600 })
  const writer = port.writable.getWriter()
  await writer.write(bytes)
  writer.releaseLock()
  await port.close()
}

export function pad(left: string, right: string, width: number): string {
  const space = Math.max(1, width - left.length - right.length)
  return (left + ' '.repeat(space) + right).slice(0, width)
}
