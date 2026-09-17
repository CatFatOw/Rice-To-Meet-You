// const BASE_URL = 'http://127.0.0.1:8000';
const BASE_URL = 'https://rice-to-meet-you-production.up.railway.app';

export interface ChatSessionState {
	city: string | null;
	date: string | null;
	messages: Record<string, unknown>[];
}

export interface ChatTranscriptEntry {
	role: string;
	text: string;
}

export interface StartChatSessionResponse {
	state: ChatSessionState;
	transcript: ChatTranscriptEntry[];
}

export interface AskChatResponse extends StartChatSessionResponse {
	answer: string;
}

function toMarketCode(city: string): string {
	const normalized = city.trim().toLowerCase();
	const aliases: Record<string, string> = {
		'kansas city': 'kansas_city',
		'los angeles': 'los_angeles',
		'san francisco bay area': 'san_francisco',
		'san francisco': 'san_francisco',
		'new york': 'new_york_nj',
		'new jersey': 'new_york_nj',
		'new york/new jersey': 'new_york_nj',
	};
	return aliases[normalized] ?? normalized.replace(/\s+/g, '_');
}

export async function startChatSession(
	city: string,
	date: string,
): Promise<StartChatSessionResponse> {
	const response = await fetch(`${BASE_URL}/chat/session`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'application/json',
		},
		body: JSON.stringify({ city: toMarketCode(city), date }),
	});

	if (!response.ok) {
		const detail = await response.text().catch(() => '');
		throw new Error(
			`Chat session request failed: ${response.status} ${response.statusText}${
				detail ? ` - ${detail}` : ''
			}`,
		);
	}

	return (await response.json()) as StartChatSessionResponse;
}

export async function askChat(
	state: ChatSessionState,
	question: string,
): Promise<AskChatResponse> {
	const response = await fetch(`${BASE_URL}/chat/ask`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'application/json',
		},
		body: JSON.stringify({ state, question }),
	});

	if (!response.ok) {
		const detail = await response.text().catch(() => '');
		throw new Error(
			`Chat request failed: ${response.status} ${response.statusText}${
				detail ? ` - ${detail}` : ''
			}`,
		);
	}

	return (await response.json()) as AskChatResponse;
}
