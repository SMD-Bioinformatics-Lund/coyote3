// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

/** Resolve the automatic theme using the device's local timezone. */
export function scheduledTheme(date = new Date()): "light" | "dark" {
  const hour = date.getHours()
  return hour >= 7 && hour < 19 ? "light" : "dark"
}
