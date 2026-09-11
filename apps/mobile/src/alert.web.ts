import type { AlertButton, AlertOptions } from "react-native";

// React Native Web's Alert is a no-op. Preserve labels and callbacks, including
// destructive confirmations, in a keyboard-accessible browser modal.
export const Alert = {
  alert(title: string, message?: string, buttons?: AlertButton[], options?: AlertOptions) {
    const dialog = document.createElement("dialog");
    dialog.setAttribute("aria-label", title);
    dialog.style.cssText = "box-sizing:border-box;width:440px;max-width:calc(100vw - 32px);max-height:85vh;overflow:auto;border:1px solid #ccc;border-radius:16px;padding:24px;font:16px system-ui;";
    const heading = document.createElement("h2");
    heading.textContent = title;
    dialog.append(heading);
    if (message) {
      const body = document.createElement("p");
      body.textContent = message;
      body.style.whiteSpace = "pre-wrap";
      dialog.append(body);
    }
    const actions = buttons?.length ? buttons : [{ text: "OK" }];
    function close() {
      dialog.close();
      dialog.remove();
    }
    for (const action of actions) {
      const button = document.createElement("button");
      button.textContent = action.text ?? "OK";
      button.style.cssText = "min-height:44px;margin:4px;padding:8px 16px;font:inherit;cursor:pointer;";
      button.autofocus = action.style === "cancel" || actions.length === 1;
      button.onclick = () => { close(); action.onPress?.(); };
      dialog.append(button);
    }
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      const cancel = actions.find((action) => action.style === "cancel");
      if (cancel || options?.cancelable) {
        close();
        cancel?.onPress?.();
        options?.onDismiss?.();
      }
    });
    document.body.append(dialog);
    dialog.showModal();
  },
};
