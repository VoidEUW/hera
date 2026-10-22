/**
 * How a rule's pattern reads to a person (#109).
 *
 * A pattern is `server__tool` with `*` and `?` for anything — exact on the wire, and not what
 * anybody wants to read. This turns the three shapes that cover nearly every rule into words
 * (*Every tool*, *Every tool from fs*, *read_file from fs*) and leaves anything stranger as the
 * pattern itself, which is honest: a glob nobody can paraphrase is one to read as written.
 *
 * It describes a pattern and **never decides what one covers** — that is the policy's matcher,
 * asked over the API, so the browser holds no second copy of the matching rules.
 */

export type Described =
	| { kind: 'everything' }
	| { kind: 'server'; server: string }
	| { kind: 'tool'; server: string; tool: string }
	| { kind: 'glob'; pattern: string };

const WILDCARDS = /[*?[]/;

export function describePattern(pattern: string): Described {
	if (pattern === '*') return { kind: 'everything' };
	const at = pattern.indexOf('__');
	if (at <= 0) return { kind: 'glob', pattern };
	const server = pattern.slice(0, at);
	const tool = pattern.slice(at + 2);
	if (WILDCARDS.test(server) || tool === '') return { kind: 'glob', pattern };
	if (tool === '*') return { kind: 'server', server };
	if (WILDCARDS.test(tool)) return { kind: 'glob', pattern };
	return { kind: 'tool', server, tool };
}

/** The `server__tool` name a pattern would have to be to cover exactly one tool — what the
 * form suggests when a tool is clicked. */
export function qualified(server: string, tool: string): string {
	return `${server}__${tool}`;
}
