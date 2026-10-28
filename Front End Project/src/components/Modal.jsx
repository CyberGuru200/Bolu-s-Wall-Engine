import { useEffect, useRef } from "react";
import Icon from "./Icon";

export default function Modal({ titleId, onClose, children, className = "" }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected)
        previousFocus.focus();
    };
  }, []);

  const trapFocus = (event) => {
    if (event.key !== "Tab") return;
    const controls = [
      ...ref.current.querySelectorAll(
        'button:not(:disabled), a[href], input, select, [tabindex="0"]',
      ),
    ];
    const first = controls[0];
    const last = controls.at(-1);
    if (
      event.shiftKey &&
      (document.activeElement === first ||
        !controls.includes(document.activeElement))
    ) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  };

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      className={`modal ${className}`}
      onKeyDown={trapFocus}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal-panel">
        <button
          className="icon-button modal-close"
          aria-label="Close dialog"
          onClick={onClose}
          autoFocus
        >
          <Icon name="close" />
        </button>
        {children}
      </div>
    </dialog>
  );
}
