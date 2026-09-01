"use client";

import type { CSSProperties, ReactNode } from "react";
import { useEffect, useRef } from "react";

type ScrollRevealProps = {
  as?: "div" | "section";
  children: ReactNode;
  className?: string;
  id?: string;
  stagger?: boolean;
};

export function ScrollReveal({
  as: Component = "div",
  children,
  className = "",
  id,
  stagger = false,
}: ScrollRevealProps) {
  const elementRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    const reducedMotion =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    if (reducedMotion || !("IntersectionObserver" in window)) {
      element.classList.add("is-revealed");
      return;
    }

    element.classList.add("scroll-reveal-enabled");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        element.classList.add("is-revealed");
        observer.disconnect();
      },
      { rootMargin: "0px 0px -8%", threshold: 0.08 },
    );
    observer.observe(element);

    return () => observer.disconnect();
  }, []);

  const classes = ["scroll-reveal", stagger && "scroll-reveal-stagger", className]
    .filter(Boolean)
    .join(" ");

  return (
    <Component
      ref={(element) => {
        elementRef.current = element;
      }}
      className={classes}
      id={id}
      style={{ "--reveal-distance": "16px" } as CSSProperties}
    >
      {children}
    </Component>
  );
}
