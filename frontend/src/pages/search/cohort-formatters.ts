// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only



export function percent(value: number | null) {
  return value == null ? "Not available" : `${value.toFixed(2)}%`;
}

export function humanSex(value: string) {
  if (value === "not_recorded") return "Unknown";
  return value.charAt(0).toUpperCase() + value.slice(1);
}
