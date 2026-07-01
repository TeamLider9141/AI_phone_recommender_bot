# Off-topic Query Guard Design

## Goal

The bot must analyze each non-command text before recommending phones. It must
not return generic phone recommendations for unrelated requests.

## Topic Classification

`QueryFilter` will expose an `is_phone_related: bool` classification. The
Gemini response schema requires this field. Directly constructed filters remain
phone-related by default for backward compatibility, while both parser paths set
the value explicitly.

- When Gemini is available, the existing structured parse request returns the
  classification together with the phone filters. This avoids a second API
  request.
- When Gemini is unavailable or fails, a deterministic fallback recognizes
  phone terms, known brands, specifications, operating systems, and common
  buying intents.
- Ambiguous input without a phone signal is treated as off-topic. Commands are
  not classified.

## Strike And Block State

State is stored per Telegram user ID in memory.

- The first off-topic request starts a 60-minute strike window and receives one
  warning.
- A second off-topic request inside that window starts a one-hour silent block.
  The second request itself receives no response.
- A phone-related request does not clear the first strike. The strike expires
  automatically 60 minutes after the first off-topic request.
- If the strike window expires before a second offense, the next off-topic
  request is treated as a new first offense.
- When a silent block expires, all strike and block state for that user is
  cleared.
- Administrators (`ADMIN_IDS`) are exempt from strikes and blocks; the rule
  only applies to regular users. (Updated 2026-07-01: originally applied to
  admins too, changed per product decision.)
- State is intentionally in memory, matching the current daily-limit
  architecture. Restarting the bot clears strikes and blocks.

The warning text is:

> Kechirasiz, hozirgi so'rovingizni e'tiborsiz qoldirishga majburmiz. Agar 1
> soat ichida yana telefonga aloqador bo'lmagan so'rov yuborsangiz, bot sizni 1
> soat davomida e'tiborsiz qoldiradi.

## Update Flow

An aiogram outer middleware checks block state before any handler.

- During an active block, messages, commands, and callback queries are ignored
  without sending or editing any Telegram message.
- Outside a block, commands continue to their existing handlers.
- Non-command text is rate-checked and classified.
- Off-topic text updates strike state but does not consume the daily phone-query
  allowance.
- Phone-related text consumes the existing daily allowance and continues
  through recommendation generation.

Classification and recommendation must share the same parsed `QueryFilter`, so
Gemini is not called twice for one accepted request.

## Error Handling

- Gemini classification failures use the deterministic classifier.
- Empty text is ignored.
- Missing Telegram user information falls back to the chat ID, matching the
  current daily-limit behavior.
- Block expiration is checked lazily when the next update arrives; no background
  scheduler is needed.

## Tests

Automated tests will cover:

- Common Uzbek, Russian, and English phone requests are accepted.
- Stories, weather, general chat, and unrelated questions are rejected.
- The first off-topic request produces the warning state.
- The second off-topic request within 60 minutes creates a one-hour block and
  produces no response.
- A second off-topic request after the strike window is another first offense.
- Commands and callbacks do not reach handlers during a block.
- Access resumes after block expiration.
- Off-topic requests do not consume the daily phone-query limit.
- Existing command, daily-limit, parser, and smoke tests remain green.
