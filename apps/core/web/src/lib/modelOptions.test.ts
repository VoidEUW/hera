import { describe, expect, it } from 'vitest';
import {
	budgetOf,
	contextLengthToSave,
	parsed,
	thinkingOn,
	withOption,
	withThinking,
	written
} from './modelOptions';

describe('parsed and written', () => {
	it('reads an empty field as no options', () => {
		expect(parsed('')).toEqual({});
		expect(parsed('   ')).toEqual({});
	});

	it('reports half-typed JSON and non-objects as null', () => {
		expect(parsed('{"a":')).toBeNull();
		expect(parsed('[1, 2]')).toBeNull();
		expect(parsed('3')).toBeNull();
	});

	it('shows an empty set as an empty field, and round-trips the rest', () => {
		expect(written({})).toBe('');
		const options = { temperature: 0.7, top_k: 40 };
		expect(parsed(written(options))).toEqual(options);
	});
});

describe('contextLengthToSave', () => {
	it('means no ceiling when blank, and refuses what is not a positive number', () => {
		expect(contextLengthToSave('')).toBeNull();
		expect(contextLengthToSave('8192')).toBe(8192);
		expect(contextLengthToSave('abc')).toBeUndefined();
		expect(contextLengthToSave('-4')).toBeUndefined();
		expect(contextLengthToSave('0')).toBeUndefined();
	});
});

describe('withOption', () => {
	it('sets and clears one key through the text', () => {
		const set = withOption('', 'temperature', 0.5);
		expect(parsed(set)).toEqual({ temperature: 0.5 });
		expect(withOption(set, 'temperature', undefined)).toBe('');
	});

	it('starts a clean object when the text is not valid JSON yet', () => {
		expect(parsed(withOption('{"half":', 'top_p', 0.9))).toEqual({ top_p: 0.9 });
	});
});

describe('withThinking', () => {
	it('merges into an existing chat_template_kwargs rather than replacing it', () => {
		const start = written({ chat_template_kwargs: { clear_thinking: false } });
		const on = parsed(withThinking(start, true));
		expect(on?.chat_template_kwargs).toEqual({ clear_thinking: false, enable_thinking: true });
	});

	it('removes a bag it has emptied', () => {
		const start = written({ chat_template_kwargs: { enable_thinking: true }, top_p: 1 });
		expect(parsed(withThinking(start, false))).toEqual({ top_p: 1 });
	});

	it('reads an untouched configuration as thinking', () => {
		expect(thinkingOn({})).toBe(true);
		expect(thinkingOn({ chat_template_kwargs: { enable_thinking: false } })).toBe(false);
	});
});

describe('budgetOf', () => {
	it('ignores zero and non-numbers', () => {
		expect(budgetOf({ thinking_budget: 2048 })).toBe(2048);
		expect(budgetOf({ thinking_budget: 0 })).toBeUndefined();
		expect(budgetOf({ thinking_budget: '2048' })).toBeUndefined();
		expect(budgetOf(null)).toBeUndefined();
	});
});
