// Fills the shared header with the logged-in user and wires the logout button.
import { logout } from "./api.js";

export function fillHeader(me) {
  for (const el of document.querySelectorAll("[data-user-name]")) el.textContent = me.name;
  for (const el of document.querySelectorAll("[data-user-initials]")) el.textContent = me.initials;
  for (const el of document.querySelectorAll("[data-user-sub]")) {
    el.textContent = me.role === "admin" ? "Hostel staff" : me.role === "faculty" ? `Faculty · ${me.department || ""}`.replace(/ · $/, "") : me.room || me.email;
  }
  for (const el of document.querySelectorAll("[data-logout]")) {
    el.addEventListener("click", logout);
  }
}
