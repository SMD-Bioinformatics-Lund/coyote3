import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { renderWithRouter } from "@/test/render"
import { Login } from "./Login"

const navigate = vi.hoisted(() => vi.fn())
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>()
  return { ...actual, useNavigate: () => navigate }
})
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }) }))

function response(body: unknown, ok = true) {
  return { ok, json: vi.fn().mockResolvedValue(body) } as unknown as Response
}

describe("Login page", () => {
  beforeEach(() => {
    navigate.mockReset()
  })

  it("loads providers, switches authentication mode, and signs in", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ providers: ["local", "ldap", "unsupported"] }))
      .mockResolvedValueOnce(response({ status: "ok" }))
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderWithRouter(<Login />, "/login")

    expect(await screen.findByRole("button", { name: "Local Account" })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "LDAP Login" }))
    expect(screen.getByLabelText("Email")).toHaveAttribute("type", "email")
    await user.type(screen.getByLabelText("Email"), "user@example.org")
    await user.type(screen.getByLabelText("Password"), "secret")
    await user.click(screen.getByRole("button", { name: "Sign in" }))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"))
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      username: "user@example.org",
      password: "secret",
      provider: "ldap",
    })
  })

  it("reveals passwords and reports rejected credentials", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(response({ providers: ["local"] }))
      .mockResolvedValueOnce(response({ detail: { error: "Invalid credentials" } }, false)))
    const user = userEvent.setup()
    renderWithRouter(<Login />)

    await screen.findByLabelText("Username")
    const password = screen.getByLabelText("Password")
    expect(password).toHaveAttribute("type", "password")
    await user.click(password.parentElement!.querySelector("button")!)
    expect(password).toHaveAttribute("type", "text")
    await user.type(screen.getByLabelText("Username"), "tester")
    await user.type(password, "wrong")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("Invalid credentials")).toBeInTheDocument()
  })

  it("reports unavailable providers and network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({}, false)))
    const unavailable = renderWithRouter(<Login />)
    expect(await screen.findByText("Login providers are unavailable")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled()
    unavailable.unmount()

    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(response({ providers: ["local"] }))
      .mockRejectedValueOnce(new Error("Network disconnected")))
    const user = userEvent.setup()
    renderWithRouter(<Login />)
    await user.type(await screen.findByLabelText("Username"), "tester")
    await user.type(screen.getByLabelText("Password"), "secret")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByText("Network disconnected")).toBeInTheDocument()
  })
})
