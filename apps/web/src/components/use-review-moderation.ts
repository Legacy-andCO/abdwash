"use client";

import { useEffect, useState } from "react";
import { getStaffContext } from "@/lib/api";

export function useReviewModerationAccess(): boolean {
  const [canModerate, setCanModerate] = useState(false);

  useEffect(() => {
    let active = true;
    void getStaffContext()
      .then((context) => {
        if (active)
          setCanModerate(
            !context.must_change_password &&
              (context.role === "manager" || context.role === "admin"),
          );
      })
      .catch(() => {
        if (active) setCanModerate(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return canModerate;
}
