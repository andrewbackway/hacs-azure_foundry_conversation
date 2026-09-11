"""AI Task platform for the Azure AI Foundry Conversation integration."""

from __future__ import annotations

import json

from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AzureFoundryConfigEntry
from .const import LOGGER
from .entity import AzureFoundryBaseLLMEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AzureFoundryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Publish an AI Task entity per ai_task_data subentry."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue
        async_add_entities(
            [AzureFoundryAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class AzureFoundryAITaskEntity(
    ai_task.AITaskEntity,
    AzureFoundryBaseLLMEntity,
):
    """Azure AI Foundry AI Task entity."""

    _attr_supported_features = ai_task.AITaskEntityFeature.GENERATE_DATA

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate-data task."""
        try:
            await self._async_handle_chat_log(chat_log, task.name, task.structure)
        except HomeAssistantError:
            raise
        except Exception:
            LOGGER.exception(
                "Unexpected error while generating data for AI Task entity %s",
                self.entity_id,
            )
            raise

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            raise HomeAssistantError(
                "Last content in chat log is not an AssistantContent"
            )

        text = chat_log.content[-1].content or ""
        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )

        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            raise HomeAssistantError(
                "Error parsing structured data from the model"
            ) from err

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )
