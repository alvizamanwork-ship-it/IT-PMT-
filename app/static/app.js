// Comment is required for Send with Feedback and Send Back.
document.addEventListener("click", function (e) {
  var b = e.target.closest("button[name=action]");
  if (!b) return;
  var c = document.getElementById("comment");
  if (c) c.required = b.hasAttribute("data-needs-comment");
});
