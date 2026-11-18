export type RawEvent = { event: string; data: string };

/**
 * Incremental Server-Sent Events parser: feed it text as it arrives from the network.
 * Chunks can end anywhere (mid-line, mid-event), so incomplete text is buffered.
 */
export class SseParser {
  private buffer = "";
  private pendingCR = false;

  push(chunk: string): RawEvent[] {
    let text = (this.pendingCR ? "\r" : "") + chunk;
    // A trailing \r may be the first half of a \r\n split across chunks: wait for the next one.
    this.pendingCR = text.endsWith("\r");
    if (this.pendingCR) text = text.slice(0, -1);
    this.buffer += text.replace(/\r\n?/g, "\n");
    const events: RawEvent[] = [];
    let end: number;
    // An event ends at a blank line; anything after the last one is still incomplete.
    while ((end = this.buffer.indexOf("\n\n")) !== -1) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      const event = parseBlock(block);
      if (event) events.push(event);
    }
    return events;
  }
}

function parseBlock(block: string): RawEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue; // comment, e.g. keep-alive ping
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length > 0 ? { event, data: data.join("\n") } : null;
}
