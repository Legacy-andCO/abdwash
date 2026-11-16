// Modals render outside the application root, so browser defaults belong on body.
import { brandColors } from "./brand-colors";

const style = document.createElement("style");
style.textContent = `
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
  input, textarea, button { font-family: inherit; }
  input, textarea { caret-color: ${brandColors.primaryPressed}; }
  ::selection { background: ${brandColors.primaryPressed}; color: ${brandColors.white}; }
  :is([role="button"], [role="tab"], button, input, textarea, select):focus-visible {
    outline: 2px solid ${brandColors.brandDark};
    outline-offset: 3px;
  }
`;
document.head.appendChild(style);
