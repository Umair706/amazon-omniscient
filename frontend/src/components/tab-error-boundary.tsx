"use client";

import React from "react";

// Catches a render error inside a tab's content so one bad AI-generated field
// can't white-screen the whole brief. React needs a class component for this —
// there is no hook equivalent. Give it key={activeTab} so switching tabs (or
// re-selecting a fixed one) clears the error and re-renders.
interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
}

export class TabErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    // Surface it in the console for debugging; the UI shows a calm fallback.
    console.error("Brief tab failed to render:", error);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="rounded-lg border border-tier3/30 bg-tier3/5 p-6 text-sm text-muted-foreground">
        This section couldn&apos;t be displayed. Part of it came back from the AI model in an
        unexpected format. The rest of the brief is fine — try another tab, or re-run the analysis.
      </div>
    );
  }
}
