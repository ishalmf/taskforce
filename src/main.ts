const view = new URLSearchParams(window.location.search).get("view");

if (view === "overlay") {
  void import("./overlay");
} else {
  void import("./settings");
}
