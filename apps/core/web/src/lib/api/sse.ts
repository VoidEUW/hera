/**
 * Reading a Server-Sent Events response.
 *
 * `EventSource` is not usable here: it only issues GET requests, and sending a message is a
 * POST with a body. So the response body is read as a stream and split on the protocol's own
 * frame boundary.
 *
 * This is a parser, and it is the *only* one in the browser — of the **transport**, not of
 * anything a model produced. That distinction is the whole rule: the previous version parsed
 * model output here and had to keep it byte-compatible with the server's parser forever. What
 * comes out of this function is already-typed JSON that the server discriminated.
 */

export interface Frame {
	/** The SSE event name, which is the event's own `type` — or `done` for the transport's
	 * closing frame carrying the persisted message. */
	name: string;
	data: unknown;
}

const DECODER = new TextDecoder();

/**
 * Yield frames from a `fetch` response until the stream ends.
 *
 * Aborting the request (or leaving the loop) closes the body, which the server sees as a
 * disconnect and turns into a `cancelled` turn with the text that did arrive.
 */
export async function* frames(response: Response): AsyncGenerator<Frame> {
	if (!response.body) throw new Error('the response carried no body');

	const reader = response.body.getReader();
	let buffer = '';

	try {
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;

			buffer += DECODER.decode(value, { stream: true });

			// A frame ends at a blank line. Anything after the last one is a partial frame and
			// stays in the buffer -- a chunk boundary lands mid-frame constantly, and treating
			// the tail as complete is how a streamed answer loses a word every few hundred.
			let boundary = buffer.indexOf('\n\n');
			while (boundary !== -1) {
				const block = buffer.slice(0, boundary);
				buffer = buffer.slice(boundary + 2);
				const frame = parse(block);
				if (frame) yield frame;
				boundary = buffer.indexOf('\n\n');
			}
		}
	} finally {
		reader.releaseLock();
	}
}

function parse(block: string): Frame | null {
	let name = 'message';
	const data: string[] = [];

	for (const line of block.split('\n')) {
		if (line.startsWith(':')) continue; // a comment, which is how a keep-alive arrives
		if (line.startsWith('event:')) name = line.slice(6).trim();
		else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
	}

	if (data.length === 0) return null;

	try {
		return { name, data: JSON.parse(data.join('\n')) };
	} catch {
		// A frame we cannot read is dropped rather than thrown: one bad frame must not end a
		// turn that is otherwise arriving fine, which is the same reasoning the server applies
		// to a malformed tool call.
		return null;
	}
}
