"use client"

import {
  InfoIcon,
  OctagonXIcon,
  TriangleAlertIcon,
} from "lucide-react"
import { CheckIcon } from "./check-icon"
import { LoaderIcon } from "./loader-icon"
import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      toastOptions={{ className: "glass-surface" }}
      icons={{
        success: <CheckIcon className="size-4" aria-hidden="true" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <LoaderIcon className="size-4" aria-hidden="true" />,
      }}
      style={
        {
          "--normal-bg": "var(--surface)",
          "--normal-text": "var(--ink)",
          "--normal-border": "var(--line)",
          "--border-radius": ".65rem",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
