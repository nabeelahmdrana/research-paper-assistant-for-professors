"use client";

import * as React from "react";

const TOAST_LIMIT = 5;
const TOAST_REMOVE_DELAY = 3000;

type ToasterToast = {
  id: string;
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
  open: boolean;
};

type Action =
  | { type: "ADD_TOAST"; toast: Omit<ToasterToast, "open"> }
  | { type: "UPDATE_TOAST"; toast: Partial<ToasterToast> & { id: string } }
  | { type: "DISMISS_TOAST"; toastId?: string }
  | { type: "REMOVE_TOAST"; toastId?: string };

interface State {
  toasts: ToasterToast[];
}

let count = 0;

function genId() {
  count = (count + 1) % Number.MAX_SAFE_INTEGER;
  return count.toString();
}

const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>();

function addToRemoveQueue(toastId: string) {
  if (toastTimeouts.has(toastId)) return;
  const timeout = setTimeout(() => {
    toastTimeouts.delete(toastId);
    dispatch({ type: "REMOVE_TOAST", toastId });
  }, TOAST_REMOVE_DELAY);
  toastTimeouts.set(toastId, timeout);
}

export function toastReducer(state: State, action: Action): State {
  switch (action.type) {
    case "ADD_TOAST":
      return {
        ...state,
        toasts: [
          { ...action.toast, open: true },
          ...state.toasts,
        ].slice(0, TOAST_LIMIT),
      };
    case "UPDATE_TOAST":
      return {
        ...state,
        toasts: state.toasts.map((t) =>
          t.id === action.toast.id ? { ...t, ...action.toast } : t
        ),
      };
    case "DISMISS_TOAST":
      return {
        ...state,
        toasts: state.toasts.map((t) =>
          t.id === action.toastId || action.toastId === undefined
            ? { ...t, open: false }
            : t
        ),
      };
    case "REMOVE_TOAST":
      if (action.toastId === undefined) {
        return { ...state, toasts: [] };
      }
      return {
        ...state,
        toasts: state.toasts.filter((t) => t.id !== action.toastId),
      };
  }
}

const listeners: Array<React.Dispatch<Action>> = [];
let memoryState: State = { toasts: [] };

function dispatch(action: Action) {
  memoryState = toastReducer(memoryState, action);
  listeners.forEach((listener) => listener(action));
}

type Toast = Omit<ToasterToast, "id" | "open">;

export function toast(props: Toast) {
  const id = genId();
  dispatch({ type: "ADD_TOAST", toast: { ...props, id } });
  setTimeout(() => {
    dispatch({ type: "DISMISS_TOAST", toastId: id });
  }, TOAST_REMOVE_DELAY - 500);
  return id;
}

export function useToast() {
  const [state, setState] = React.useState<State>(memoryState);

  React.useEffect(() => {
    const listener: React.Dispatch<Action> = () => {
      setState({ ...memoryState });
    };
    listeners.push(listener);
    return () => {
      const index = listeners.indexOf(listener);
      if (index > -1) listeners.splice(index, 1);
    };
  }, []);

  const dismissToast = React.useCallback(
    (toastId?: string) => {
      dispatch({ type: "DISMISS_TOAST", toastId });
      if (toastId) {
        addToRemoveQueue(toastId);
      }
    },
    []
  );

  return {
    ...state,
    toast,
    dismiss: dismissToast,
  };
}
