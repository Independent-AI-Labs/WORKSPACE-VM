import type { TuiPlugin } from "@opencode-ai/plugin/tui";
import { readModels, replaceTopModel, type ModelSelector } from "./model-select.ts";

interface TuiProvider {
  id: string;
  name?: string;
  models?: Record<string, { name?: string }>;
}

const plugin: TuiPlugin = async (api) => {
  const unregister = api.command?.register(() => [{
    title: "Moderator model",
    value: "moderator.model",
    description: "Select the top response moderator model",
    slash: { name: "moderator" },
    onSelect: async (dialog) => {
      const providers = api.state.provider as readonly TuiProvider[];
      const options = providers.flatMap((provider) => {
        const models = provider.models ?? {};
        return Object.entries(models).map(([modelID, model]) => ({
          title: `${provider.name ?? provider.id} / ${model.name ?? modelID}`,
          value: { providerID: provider.id, modelID },
          description: provider.id,
        }));
      });
      if (options.length === 0) {
        api.ui.toast({ title: "Moderator", message: "No OpenCode models are available.", variant: "error" });
        return;
      }
      const current = await readModels();
      const render = () => api.ui.DialogSelect<ModelSelector>({
        title: "Select moderator model",
        current: current[0],
        options,
        onSelect: async (option) => {
          try {
            await replaceTopModel(option.value);
            api.ui.toast({ title: "Moderator", message: `Top model: ${option.value.providerID}/${option.value.modelID}`, variant: "success" });
          } catch (error) {
            api.ui.toast({ title: "Moderator", message: error instanceof Error ? error.message : String(error), variant: "error" });
          }
          dialog?.clear();
        },
      });
      if (dialog !== undefined) dialog.replace(render);
      else api.ui.dialog.replace(render);
    },
  }]);
  if (unregister !== undefined) api.lifecycle.onDispose(unregister);
};

export default { id: "moderator-tui", tui: plugin };
