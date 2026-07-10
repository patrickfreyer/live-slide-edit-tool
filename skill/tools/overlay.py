import json

OVERLAY_TEMPLATE = """<style id="__live-edit-style__">
[data-edit-target] { outline: 2px dashed transparent; transition: outline-color .2s; }
[data-edit-target]:hover { outline-color: #94a3b8; }
[data-edit-target].__edit-pending { outline: 2px solid #eab308; }
[data-edit-target].__edit-inprogress { outline: 2px solid #3b82f6; }
[data-edit-target].__edit-resolved { outline: 2px solid #22c55e; }
#__live-edit-comment-icon__ {
  position: absolute; z-index: 999999; display: none; cursor: pointer;
  background: #fff; border: 1px solid #94a3b8; border-radius: 50%%;
  width: 22px; height: 22px; font-size: 12px; line-height: 20px; text-align: center;
}
#__live-edit-note-btn__ {
  position: fixed; bottom: 16px; right: 16px; z-index: 999999;
  background: #1e293b; color: #fff; border: none; border-radius: 24px;
  padding: 10px 16px; font: 14px sans-serif; cursor: pointer;
}
#__live-edit-note-box__ {
  position: fixed; z-index: 999999; background: #fff; border: 1px solid #94a3b8;
  border-radius: 8px; padding: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.15); display: none;
}
#__live-edit-note-box__ textarea { width: 240px; height: 60px; font: 13px sans-serif; }
#__live-edit-note-box__ button { margin-top: 4px; font: 12px sans-serif; }
#__live-edit-notes-panel__ {
  position: fixed; bottom: 60px; right: 16px; z-index: 999999; width: 260px;
  max-height: 200px; overflow-y: auto; font: 12px sans-serif;
}
#__live-edit-notes-panel__ .__note-item__ {
  background: #fff; border: 1px solid #cbd5e1; border-radius: 6px;
  padding: 6px 8px; margin-bottom: 6px;
}
</style>
<script id="__live-edit-script__">
(function(){
  var FILE = %(file)s;
  var EDIT_TAGS = ["P","LI","H1","H2","H3","H4","H5","H6","TD","TH","SPAN","BLOCKQUOTE"];
  var selectorToId = {};
  var noteIdToItemEl = {};
  var currentCommentSelector = null;
  var currentCommentEl = null;
  var reloadTriggered = false;

  function computeSelector(el){
    var path = [];
    var node = el;
    while (node && node.nodeType === 1 && node.tagName !== "BODY"){
      var idx = 1, sib = node;
      while ((sib = sib.previousElementSibling)){ if (sib.tagName === node.tagName) idx++; }
      path.unshift(node.tagName.toLowerCase() + ":nth-of-type(" + idx + ")");
      node = node.parentElement;
    }
    return path.join(">");
  }

  function findBySelector(selector){
    try { return document.querySelector(selector.split(">").join(" > ")); }
    catch(e){ return null; }
  }

  var lastText = {};
  function onBlur(e){
    var el = e.target;
    var sel = el.dataset.editSelector;
    var before = lastText[sel] !== undefined ? lastText[sel] : el.textContent;
    var after = el.textContent;
    lastText[sel] = after;
    if (before === after) return;
    submitEdit("text", sel, before, after, null, el);
  }

  function showCommentIcon(el){
    var icon = document.getElementById("__live-edit-comment-icon__");
    var rect = el.getBoundingClientRect();
    icon.style.left = (rect.right + window.scrollX + 4) + "px";
    icon.style.top = (rect.top + window.scrollY) + "px";
    icon.style.display = "block";
    icon.dataset.forSelector = el.dataset.editSelector;
  }

  function hideCommentIconSoon(){
    setTimeout(function(){
      var icon = document.getElementById("__live-edit-comment-icon__");
      if (!icon.matches(":hover")) icon.style.display = "none";
    }, 200);
  }

  function markEditable(){
    EDIT_TAGS.forEach(function(tag){
      Array.prototype.forEach.call(document.getElementsByTagName(tag), function(el){
        if (el.children.length === 0 && el.textContent.trim().length > 0 && !el.dataset.editSelector){
          el.setAttribute("contenteditable", "true");
          el.setAttribute("data-edit-target", "1");
          el.dataset.editSelector = computeSelector(el);
          lastText[el.dataset.editSelector] = el.textContent;
          el.addEventListener("blur", onBlur);
          el.addEventListener("mouseenter", function(){ showCommentIcon(el); });
          el.addEventListener("mouseleave", hideCommentIconSoon);
        }
      });
    });
  }

  function submitEdit(type, selector, before, after, note, el){
    fetch("/__edit__", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({file: FILE, type: type, selector: selector, before: before, after: after, note: note})
    }).then(function(r){ return r.json(); }).then(function(data){
      if (!data.id) return;
      if (selector){
        selectorToId[selector] = data.id;
        var target = el || findBySelector(selector);
        if (target) target.classList.add("__edit-pending");
      }
      if (type === "note"){
        addNoteItem(data.id, note);
      }
      pollStatus();
    });
  }

  function addNoteItem(id, text){
    var panel = document.getElementById("__live-edit-notes-panel__");
    if (!panel) return;
    var item = document.createElement("div");
    item.className = "__note-item__";
    item.textContent = text + " — pending";
    panel.appendChild(item);
    noteIdToItemEl[id] = item;
  }

  // Invariant: hydrateFromServer() (below) filters out ids whose status is
  // already "resolved" before ever adding them to selectorToId/noteIdToItemEl,
  // so the very first applyStatuses() call made from hydrateFromServer can
  // never see a resolved id transition here and can never trigger a reload.
  // Do not remove/change that filtering without re-verifying this invariant --
  // it's what prevents an infinite reload loop on page load.
  function applyStatuses(map){
    var anyUnresolved = false;
    var justResolved = false;
    Object.keys(selectorToId).forEach(function(selector){
      var id = selectorToId[selector];
      var info = map[id];
      if (!info) return;
      if (info.status !== "resolved") anyUnresolved = true;
      else justResolved = true;
      var target = findBySelector(selector);
      if (!target) return;
      target.classList.remove("__edit-pending", "__edit-inprogress", "__edit-resolved");
      target.classList.add("__edit-" + info.status.replace("in-progress", "inprogress"));
    });
    Object.keys(noteIdToItemEl).forEach(function(id){
      var info = map[id];
      if (!info) return;
      if (info.status !== "resolved") anyUnresolved = true;
      else justResolved = true;
      var item = noteIdToItemEl[id];
      item.textContent = item.textContent.replace(/ — .*/, " — " + info.status);
    });
    if (justResolved && !reloadTriggered){
      reloadTriggered = true;
      window.location.reload();
      return false;
    }
    return anyUnresolved;
  }

  var statusTimer = null;
  function pollStatus(){
    if (statusTimer) return;
    statusTimer = setInterval(function(){
      fetch("/__status__").then(function(r){ return r.json(); }).then(function(map){
        var anyUnresolved = applyStatuses(map);
        if (!anyUnresolved){ clearInterval(statusTimer); statusTimer = null; }
      });
    }, 1500);
  }

  function openNoteBox(rect, forComment){
    var noteBox = document.getElementById("__live-edit-note-box__");
    noteBox.style.left = (rect.left - 240) + "px";
    noteBox.style.top = (rect.top - 80) + "px";
    noteBox.style.display = "block";
    var textarea = noteBox.querySelector("textarea");
    textarea.placeholder = forComment ? "Comment on this element" : "What should Claude change?";
    textarea.value = "";
    textarea.focus();
  }

  // Always created, in every document the overlay is injected into (shell
  // AND each iframe): the per-element comment icon and the note box it
  // opens. Both the margin-comment flow (icon click) and the freeform note
  // flow (top-document-only "+ Note for Claude" button, see buildFloatingUi)
  // share this same note box instance to submit to /__edit__.
  function buildCommentUi(){
    var commentIcon = document.createElement("div");
    commentIcon.id = "__live-edit-comment-icon__";
    commentIcon.textContent = "\\uD83D\\uDCAC";
    document.body.appendChild(commentIcon);

    var noteBox = document.createElement("div");
    noteBox.id = "__live-edit-note-box__";
    noteBox.innerHTML = '<textarea placeholder="What should Claude change?"></textarea><br>'
      + '<button data-action="submit">Submit</button> <button data-action="cancel">Cancel</button>';
    document.body.appendChild(noteBox);

    commentIcon.addEventListener("mouseenter", function(){
      commentIcon.style.display = "block";
    });
    commentIcon.addEventListener("mouseleave", function(){
      commentIcon.style.display = "none";
    });
    commentIcon.addEventListener("click", function(){
      currentCommentSelector = commentIcon.dataset.forSelector;
      currentCommentEl = findBySelector(currentCommentSelector);
      openNoteBox(commentIcon.getBoundingClientRect(), true);
    });

    noteBox.addEventListener("click", function(e){
      var action = e.target.getAttribute("data-action");
      if (action === "submit"){
        var text = noteBox.querySelector("textarea").value.trim();
        if (text){
          if (currentCommentSelector){
            submitEdit("comment", currentCommentSelector, null, null, text, currentCommentEl);
          } else {
            submitEdit("note", null, null, null, text, null);
          }
        }
        noteBox.style.display = "none";
      } else if (action === "cancel"){
        noteBox.style.display = "none";
      }
    });
  }

  // Top-document-only: the floating "+ Note for Claude" trigger button and
  // the notes-list panel. These are global, unanchored affordances -- if
  // every iframe in a shell+iframe deck rendered its own copy, the page
  // would show one per document simultaneously. Gated by window.self ===
  // window.top in init() below.
  function buildFloatingUi(){
    var panel = document.createElement("div");
    panel.id = "__live-edit-notes-panel__";
    document.body.appendChild(panel);

    var noteBtn = document.createElement("button");
    noteBtn.id = "__live-edit-note-btn__";
    noteBtn.textContent = "+ Note for Claude";
    document.body.appendChild(noteBtn);

    noteBtn.addEventListener("click", function(){
      currentCommentSelector = null;
      currentCommentEl = null;
      openNoteBox(noteBtn.getBoundingClientRect(), false);
    });
  }

  function hydrateFromServer(){
    fetch("/__status__").then(function(r){ return r.json(); }).then(function(map){
      Object.keys(map).forEach(function(id){
        var info = map[id];
        if (info.file !== FILE) return;
        if (info.status === "resolved") return;
        if (info.selector){
          var target = findBySelector(info.selector);
          if (target){
            selectorToId[info.selector] = id;
            return;
          }
        }
        if (!noteIdToItemEl[id]){
          addNoteItem(id, info.note || ("(no longer anchored — selector: " + info.selector + ")"));
        }
      });
      var anyUnresolved = applyStatuses(map);
      if (anyUnresolved) pollStatus();
    });
  }

  function init(){
    buildCommentUi();
    if (window.self === window.top){
      buildFloatingUi();
    }
    markEditable();
    hydrateFromServer();
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
</script>
"""


def build_overlay_snippet(file_rel_path):
    # json.dumps() escapes quotes/backslashes so the value is a valid JS
    # string literal, but it does NOT escape `/`. If file_rel_path contains
    # a literal `</script>`, that survives json.dumps() untouched and closes
    # the surrounding <script> tag at the HTML-parser level -- regardless of
    # JS-string escaping -- letting arbitrary markup/script follow. Escaping
    # `<` as its JS unicode escape prevents `</script>`, `<!--`, and similar
    # HTML-parser-level breakouts while still decoding to the same string
    # inside the <script> block.
    escaped = json.dumps(file_rel_path).replace("<", "\\u003C")
    return OVERLAY_TEMPLATE % {"file": escaped}


def inject_overlay(html, file_rel_path):
    """Insert the editable overlay into an HTML document, just before </body>.

    Appends at the end if no closing body tag is found (e.g. a bare fragment).
    """
    snippet = build_overlay_snippet(file_rel_path)
    marker = "</body>"
    idx = html.rfind(marker)
    if idx == -1:
        return html + snippet
    return html[:idx] + snippet + html[idx:]
