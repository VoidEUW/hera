/**
 * Her prose, rendered: Markdown with GitHub tables, and TeX through KaTeX.
 *
 * This is not the parser the project rules forbid, and the difference is worth being precise
 * about. That rule is about **structure**: what she *did* — a tool call, an emotion, a skill,
 * a permission request — never comes back out of text. It arrives as an event variant with
 * fields on it (ADR 10), and nothing in the browser recovers meaning from prose. What arrives
 * here is one message's worth of prose written for a person to read, and Markdown is the
 * notation it was written in. Drawing it as unstyled paragraphs does not avoid a parse; it
 * moves the parse into the reader's head. See ADR 11.
 *
 * Two rules hold that seam shut:
 *
 * - **Nothing here reads meaning back out.** A heading is a heading and a fence is a fence.
 *   No branch in this file learns what a skill or a tool is, and no event is ever reconstructed
 *   from text. If a future change wants one, the answer is an event variant.
 * - **The output is sanitised before it reaches `{@html}`.** The string came from a model, and
 *   a model can be talked into emitting a `<script>` by the page it was asked to read.
 */

import DOMPurify from 'dompurify';
import katex from 'katex';
import { Marked, type TokenizerAndRendererExtension, type Tokens } from 'marked';

import { t } from '$lib/i18n';

/** A formula, in either of the two forms TeX is written in. */
interface Math extends Tokens.Generic {
	raw: string;
	text: string;
	display: boolean;
}

/** `$$…$$` or `\[…\]`, alone on its own lines. */
const BLOCK = /^ {0,3}(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])[ \t]*(?:\n+|$)/;

/** `$…$` or `\(…\)`, inside a sentence. */
const INLINE = /^(?:\$((?:[^$\\\n]|\\.)+?)\$|\\\(([\s\S]+?)\\\))/;

function escape(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

function tex(token: Math): string {
	try {
		return katex.renderToString(token.text, {
			displayMode: token.display,
			// A formula she got slightly wrong is drawn in red with its source legible, which
			// is what a person needs in order to say so. Throwing would lose the whole answer
			// around it.
			throwOnError: false,
			strict: false,
			trust: false,
			output: 'htmlAndMathml'
		});
	} catch {
		return escape(token.raw);
	}
}

const blockMath: TokenizerAndRendererExtension = {
	name: 'blockMath',
	level: 'block',
	start: (src: string) => src.match(/\$\$|\\\[/)?.index,
	tokenizer(src: string) {
		const found = BLOCK.exec(src);
		if (!found) return undefined;
		const body = (found[1] ?? found[2]).trim();
		if (!body) return undefined;
		return { type: 'blockMath', raw: found[0], text: body, display: true };
	},
	renderer: (token) => tex(token as Math)
};

const inlineMath: TokenizerAndRendererExtension = {
	name: 'inlineMath',
	level: 'inline',
	start: (src: string) => src.match(/\$|\\\(/)?.index,
	tokenizer(src: string) {
		const found = INLINE.exec(src);
		if (!found) return undefined;
		const dollars = found[1] !== undefined;
		const body = found[1] ?? found[2];
		if (!body.trim()) return undefined;
		// "It costs $5 and $10" is not an equation, and a price is the commonest false
		// positive there is. The tells are reliable: TeX does not open or close on a space,
		// and a closing `$` followed by a digit is a second amount rather than the end of a
		// formula. `\(…\)` needs none of this, which is why it is the delimiter to prefer.
		if (dollars && (/^\s|\s$/.test(body) || /^\d/.test(src.slice(found[0].length)))) {
			return undefined;
		}
		return { type: 'inlineMath', raw: found[0], text: body.trim(), display: false };
	},
	renderer: (token) => tex(token as Math)
};

const marked = new Marked({ gfm: true, breaks: true });

marked.use({
	extensions: [blockMath, inlineMath],
	tokenizer: {
		// A line of dashes is a rule, never a heading. Markdown's setext form makes `---`
		// promote the line *above* it to an `<h2>`, so the commonest way a model separates two
		// thoughts would silently shout whichever sentence it had just finished. Disabled, the
		// same line falls through to a thematic break: a hairline with air around it, which
		// reads as either a separator or a gap depending on what she meant by it.
		lheading: () => undefined
	},
	renderer: {
		code(token: Tokens.Code) {
			// A fenced block is the one thing on screen that exists to be taken somewhere else,
			// so it gets a button. The markup is a `figure` with a caption bar: the language on
			// the left, the copy on the right. What it copies is read off the DOM by
			// `Prose.svelte` rather than carried in a `data-` attribute — a second copy of the
			// code in an attribute is a second thing to escape correctly, and it would double
			// the size of every answer containing a program.
			const language = (token.lang ?? '').split(/\s+/)[0];
			const classes = language ? ` class="language-${escape(language)}"` : '';
			return [
				'<figure class="code">',
				'<figcaption>',
				`<span class="lang">${escape(language)}</span>`,
				`<button class="copy" type="button" aria-label="${escape(t.message.copy)}">`,
				`${escape(t.message.copy)}</button>`,
				'</figcaption>',
				`<pre><code${classes}>${escape(token.text)}</code></pre>`,
				'</figure>'
			].join('');
		},

		link(token: Tokens.Link) {
			// Her links leave the application rather than navigating it away from a
			// conversation, and `noopener` is not optional on a target of `_blank`.
			const text = this.parser.parseInline(token.tokens);
			const title = token.title ? ` title="${escape(token.title)}"` : '';
			return `<a href="${escape(token.href)}"${title} target="_blank" rel="noopener noreferrer">${text}</a>`;
		}
	}
});

/**
 * One string of prose as safe HTML.
 *
 * Called on every `text_delta` while a turn streams, so it runs on prose that is legitimately
 * half-written: an open fence, a `$` with no partner, a table missing its last row. Markdown
 * degrades into text on all three, which is the behaviour that matters — the fragment renders
 * as what it is so far and settles when the rest arrives.
 */
export function render(source: string): string {
	const html = marked.parse(source ?? '', { async: false });
	return DOMPurify.sanitize(html, {
		// KaTeX draws a formula twice: HTML for eyes, MathML for a screen reader.
		USE_PROFILES: { html: true, mathMl: true, svg: true },
		ADD_ATTR: ['target']
	});
}
