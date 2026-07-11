# PronounceAI Privacy Notice

## Summary

PronounceAI processes short English recordings to provide pronunciation coaching. This notice explains what data is processed, why it is processed, which processors are involved, how long results are kept, and how deletion works.

## What We Collect

- Audio recordings uploaded or recorded in the browser.
- Recognized transcript text generated from the recording.
- Derived pronunciation scores, diagnostics, coaching text, and practice guidance.
- Anonymous session identifier stored in the browser and sent as `X-Session-Id`.

Transcript content can contain identifying personal data when a speaker says their name, institution, city, employer, or similar details. Raw audio deletion does not remove that reality, so transcript content must be treated as personal data.

## Purpose

This data is processed only to:

- assess pronunciation quality
- generate coaching explanations
- build practice guidance
- show session history to the same browser session

The application does not use this content for advertising or unrelated secondary use.

## Processors and Residency

- Azure Speech: used for speech recognition and pronunciation assessment. In this repository, the configured region is Central India.
- Groq: used to generate learner-facing coaching text from transcript and diagnostic context. This is a separate sub-processor and is not India-hosted.
- Hosting provider: the final production hosting provider is deployment-specific and must be named in the deployed service's legal notice before launch.

Because Groq receives transcript content and derived diagnostic context, compliance materials should not imply that all processing stays within India.

## Retention

- Raw audio files are deleted immediately after processing completes.
- Stored attempt results, including transcripts, scores, coaching payloads, and raw Azure payload JSON attached to a row, are retained for up to 90 days from creation or until the user deletes them, whichever comes first.
- A daily automated retention job purges expired rows from the `attempts` table.

## Deletion

- Users can delete a single attempt or their full history from the UI while the same browser session identifier is still available.
- If local browser storage is cleared, in-app deletion access may be lost for that session's rows.
- The automated retention purge exists as a backstop so those rows do not persist indefinitely.

## Contact

For privacy, deletion, or data-related requests, contact imdanishakhtar7@gmail.com.
