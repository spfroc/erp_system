import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("requires login before rendering the dashboard", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "登录系统" })).toBeInTheDocument();
    const accountInput = screen.getByLabelText("手机号或姓名");
    const passwordInput = screen.getByLabelText("密码");
    expect(accountInput).toHaveValue("");
    expect(passwordInput).toHaveValue("");
    expect(screen.queryByText(/老板 ·/)).not.toBeInTheDocument();
    fireEvent.change(accountInput, { target: { value: "18600000001" } });
    fireEvent.change(passwordInput, { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByRole("heading", { name: "总览" })).toBeInTheDocument();
  });
});
