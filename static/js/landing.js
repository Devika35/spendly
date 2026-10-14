// landing.js — "See how it works" video modal

(function () {
    var modal = document.getElementById("video-modal");
    var openBtn = document.getElementById("video-modal-open");
    var closeBtn = document.getElementById("video-modal-close");
    var iframe = document.getElementById("video-modal-iframe");

    if (!modal || !openBtn || !closeBtn || !iframe) return;

    function openModal() {
        // Load the video only when opened, so it never plays in the background
        iframe.src = iframe.dataset.src;
        modal.hidden = false;
        document.body.style.overflow = "hidden";
        closeBtn.focus();
    }

    function closeModal() {
        // Clearing the src unloads the player, which stops playback
        iframe.src = "";
        modal.hidden = true;
        document.body.style.overflow = "";
        openBtn.focus();
    }

    openBtn.addEventListener("click", openModal);
    closeBtn.addEventListener("click", closeModal);

    // Clicking the dark overlay (outside the dialog) closes the modal
    modal.addEventListener("click", function (e) {
        if (e.target === modal) closeModal();
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !modal.hidden) closeModal();
    });
})();
