/**
 * @vitest-environment jsdom
 *
 * What the renderer has to get right is mostly what it has to *refuse*: a price is not a
 * formula, a line of dashes is not a heading, and nothing a model writes may become a script.
 */

import { describe, expect, it } from 'vitest';

import { render } from './markdown';

describe('markdown', () => {
	it('renders the structure a model actually writes', () => {
		const html = render('## Kerberos\n\n- a ticket\n- a service\n\n`kinit` then `klist`');
		expect(html).toContain('<h2>Kerberos</h2>');
		expect(html).toContain('<li>a ticket</li>');
		expect(html).toContain('<code>kinit</code>');
	});

	it('keeps a fenced block whole, with its language and a way to take it', () => {
		const html = render('```python\nprint("hi")\n```');
		expect(html).toContain('<pre>');
		expect(html).toContain('language-python');
		expect(html).toContain('print("hi")');
		// The button survives sanitising, which is the part worth asserting: DOMPurify is
		// what stands between a model and the DOM, and it has opinions about buttons.
		expect(html).toContain('button');
		expect(html).toContain('class="copy"');
	});

	it('gives an unlabelled fence the same frame', () => {
		const html = render('```\nplain\n```');
		expect(html).toContain('class="copy"');
		expect(html).not.toContain('language-');
	});

	it('renders a table', () => {
		const html = render('| a | b |\n|---|---|\n| 1 | 2 |');
		expect(html).toContain('<table>');
		expect(html).toContain('<td>1</td>');
	});

	it('breaks a single newline, because that is how prose is typed', () => {
		expect(render('one\ntwo')).toContain('<br>');
	});

	it('draws a rule for a line of dashes and never a heading', () => {
		const html = render('A thought.\n\n---\n\nA second one.');
		expect(html).toContain('<hr>');
		expect(html).not.toContain('<h2');
	});

	it('draws a rule even with no blank line above it', () => {
		// The setext trap: without `lheading` disabled this promotes "A thought." to an <h2>.
		const html = render('A thought.\n---\nA second one.');
		expect(html).toContain('<hr>');
		expect(html).not.toContain('<h2');
	});

	it('renders inline TeX in both notations', () => {
		expect(render(String.raw`the identity \(e^{i\pi} + 1 = 0\) holds`)).toContain('katex');
		expect(render('the identity $e^{i\\pi} + 1 = 0$ holds')).toContain('katex');
	});

	it('renders display TeX in both notations', () => {
		expect(render('$$\n\\int_0^1 x^2\\,dx\n$$')).toContain('katex-display');
		expect(render(String.raw`\[ \int_0^1 x^2\,dx \]`)).toContain('katex-display');
	});

	it('leaves prices alone', () => {
		const html = render('It costs $5 and the other one $10.');
		expect(html).not.toContain('katex');
		expect(html).toContain('$5');
	});

	it('leaves TeX inside a code fence as text', () => {
		const html = render('```\n$x^2$\n```');
		expect(html).not.toContain('katex');
		expect(html).toContain('$x^2$');
	});

	it('draws a broken formula rather than losing the answer around it', () => {
		const html = render(String.raw`before \(\frac{1}{\) after`);
		expect(html).toContain('before');
		expect(html).toContain('after');
	});

	it('strips a script the model was talked into writing', () => {
		const html = render('hello <script>alert(1)</script> there');
		expect(html).not.toContain('<script');
		expect(html).toContain('hello');
	});

	it('strips an event handler', () => {
		expect(render('<img src=x onerror="alert(1)">')).not.toContain('onerror');
	});

	it('refuses a javascript: link', () => {
		const html = render('[click](javascript:alert(1))');
		expect(html).not.toContain('javascript:');
	});

	it('opens a real link in a new tab, safely', () => {
		const html = render('[katex](https://katex.org)');
		expect(html).toContain('href="https://katex.org"');
		expect(html).toContain('target="_blank"');
		expect(html).toContain('rel="noopener noreferrer"');
	});

	it('survives the half-written prose a stream is made of', () => {
		for (const partial of ['```py', '```py\nprint(', 'a $', String.raw`a \(`, '| a |', '#']) {
			expect(() => render(partial)).not.toThrow();
		}
	});

	it('renders nothing for nothing', () => {
		expect(render('')).toBe('');
	});
});
