import { describe, expect, it } from "vitest";

import { SseParser } from "@/lib/sse";

function parseAll(...chunks: string[]) {
  const parser = new SseParser();
  return chunks.flatMap((chunk) => parser.push(chunk));
}

describe("SseParser", () => {
  it("parses a complete event", () => {
    expect(parseAll('event: token\ndata: {"text": "Hi"}\n\n')).toEqual([
      { event: "token", data: '{"text": "Hi"}' },
    ]);
  });

  it("waits for the blank line before emitting an event", () => {
    const parser = new SseParser();

    expect(parser.push("event: token\ndata: 1\n")).toEqual([]);
    expect(parser.push("\n")).toEqual([{ event: "token", data: "1" }]);
  });

  it("reassembles an event split across network chunks, even mid-line", () => {
    expect(parseAll("eve", "nt: sta", 'tus\ndata: {"step": "re', 'trieve"}\n', "\n")).toEqual([
      { event: "status", data: '{"step": "retrieve"}' },
    ]);
  });

  it("parses several events from one chunk", () => {
    expect(parseAll("event: a\ndata: 1\n\nevent: b\ndata: 2\n\n")).toEqual([
      { event: "a", data: "1" },
      { event: "b", data: "2" },
    ]);
  });

  it("ignores keep-alive comments", () => {
    expect(parseAll(": ping\n\nevent: a\ndata: 1\n\n")).toEqual([{ event: "a", data: "1" }]);
  });

  it("accepts CRLF line endings", () => {
    expect(parseAll("event: a\r\ndata: 1\r\n\r\n")).toEqual([{ event: "a", data: "1" }]);
  });

  it("does not mistake a CRLF split across chunks for a blank line", () => {
    expect(parseAll("event: a\r", "\ndata: 1\r\n\r\n")).toEqual([{ event: "a", data: "1" }]);
  });

  it("joins multiple data lines with newlines", () => {
    expect(parseAll("event: a\ndata: line 1\ndata: line 2\n\n")).toEqual([
      { event: "a", data: "line 1\nline 2" },
    ]);
  });

  it('defaults the event name to "message"', () => {
    expect(parseAll("data: 1\n\n")).toEqual([{ event: "message", data: "1" }]);
  });
});
