// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { useContext } from "react"
import { NotificationContext } from "./notification-context"

export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error("useNotifications must be used inside NotificationProvider")
  }
  return context
}
