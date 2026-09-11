# OpenTDB Card

A standalone Lovelace card for the [Open Trivia Database Home Assistant integration](https://github.com/andrewbackway/hacs-opentdb).

## Installation

[![Open your Home Assistant instance and show the add repository dialog](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=andrewbackway&repository=hacs-opentdb-card&category=dashboard)
[![Install OpenTDB Card with HACS](https://img.shields.io/badge/HACS-Install-41BDF5?logo=homeassistant&logoColor=white)](https://github.com/andrewbackway/hacs-opentdb-card)

Add `https://github.com/andrewbackway/hacs-opentdb-card` as a custom HACS repository with the category **Dashboard**. Install **Open Trivia Database Card**, then reload your browser.

The card expects the integration to be installed and configured first. The integration exposes one primary Quiz sensor per configured quiz; point each card at the quiz you want. The card targets that entity and gets question, score, elapsed time, feedback, and player data through authenticated WebSocket commands. Add it to a dashboard as a Manual card:

```yaml
type: custom:opentdb-card
quiz_id: family_trivia
title: Evening trivia
read_out_question: true
tts_engine: tts.home_assistant_cloud
media_player: media_player.kitchen_speaker
```

### Configuration

| Option | Required | Description | Default |
| --- | --- | --- | --- |
| `type` | Yes | Must be `custom:opentdb-card`. | None |
| `quiz_id` | Yes | Select the OpenTDB quiz in the Home Assistant entity picker. When you run several quizzes, pick the sensor for the quiz this card should show. The selected quiz entity ID is used as the integration's quiz identifier; the card does not read its sensor state. | None |
| `title` | No | Heading shown at the top of the card. | `Open Trivia DB Quiz` |
| `sound` | No | Play WebAudio sound effects (buzzer, chime, fanfare). | `true` |
| `shake` | No | Shake the question on a wrong answer. Always disabled when the browser requests reduced motion. | `true` |
| `show_new_quiz_button` | No | Show a **New quiz** button on the completion screen. This overrides the one-quiz-per-day rule: pressing it makes the integration generate a fresh question set for everyone. When off, the completion screen shows "Come back tomorrow" instead. | `false` |
| `read_out_question` | No | Read each question and its labeled potential answers through Home Assistant TTS. Shows a replay button for the active question. | `false` |
| `tts_engine` | No | TTS entity used by `tts.speak` when `read_out_question` is enabled. | None |
| `media_player` | No | Media player that receives TTS audio and is stopped when an answer is selected. | None |

When narration is enabled, configure both the TTS engine and media player. The
card uses the Home Assistant `tts.speak` service with this equivalent syntax:

```yaml
action: tts.speak
target:
	entity_id: tts.home_assistant_cloud
data:
	media_player_entity_id: media_player.kitchen_speaker
	message: "Question: What is the capital of France? Answers: A. Paris. B. Rome. C. Berlin. D. Madrid."
```

Each newly displayed question is read once. The replay button reads the active
question and all labeled answers again. Selecting an answer stops the
configured media player before the answer is submitted. Missing or unavailable
TTS configuration does not prevent normal quiz play.

The card opens an authenticated per-user session through the integration's WebSocket API. The active question, current progress, feedback, score, and completion state are held in the card's JavaScript instance and are never read from shared sensor state. The OpenTDB integration must be installed, loaded, and up to date for these actions to work.

The card displays the current question and shuffled answers, submits answers for the logged-in Home Assistant user, shows feedback with points earned (speed and streak bonuses), plays sound effects, shakes on a wrong answer, advances after a short delay, and finishes with a results screen showing the final percentage, elapsed time, and leaderboard. By default there is one quiz per day, so the results screen invites players to come back tomorrow; enable `show_new_quiz_button` to allow starting a fresh quiz on demand.

## Development

```powershell
npm ci
npm run build
```

The compiled card is written to `opentdb-card.js`, which is the root-level file HACS expects from `hacs.json`.
