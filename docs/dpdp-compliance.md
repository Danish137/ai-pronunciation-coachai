# PronounceAI DPDP Compliance Notes

## Current Position

This repository now supports a narrower and more defensible DPDP posture for pronunciation coaching workloads:

- explicit opt-in consent is required before analysis
- the consent flow links to a Privacy Notice
- raw audio is transient and deleted after processing
- retained data is limited to transcripts, scores, and coaching results
- automatic retention purges old attempt rows after 90 days
- Azure Speech is configured for Central India
- Groq is named explicitly as a separate sub-processor for coaching-text generation

## Consent

- The consent checkbox is unchecked by default.
- The checkbox text discloses that both the recording and transcript are processed.
- The Privacy Notice explains processors, retention, deletion, and contact details.
- Consent acceptance is stored on the attempt row with a recorded timestamp.

## Storage and Retention

- Audio files are written to temporary storage only for analysis and then deleted.
- The `attempts` table retains transcript content, scores, coaching payloads, and related attempt metadata.
- A daily APScheduler retention job purges rows older than 90 days based on `created_at`.
- Purge logs record deleted row counts only.

## Deletion

- Users can delete individual attempts or all history while they still control the browser session UUID.
- Attempt-level read, delete, and raw-Azure endpoints are scoped by both `session_id` and `attempt_id`.
- Automatic expiry prevents indefinite retention if a user loses the local session identifier.

## Residency and Cross-Border Processing

- Azure Speech processing is configured for Central India.
- Coaching-text generation sends transcript content and derived diagnostics to Groq.
- Groq is not India-hosted, so cross-border processing must be disclosed rather than implied away.

## Residual Limitation

The app still relies on an anonymous browser session UUID rather than authenticated user identity. That is acceptable for lightweight session scoping, but it is not equivalent to a strong account-based data access model.
