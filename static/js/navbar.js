document.addEventListener("DOMContentLoaded", () => {
// Mobile hamburger
const toggleBtn = document.getElementById("menu-toggle");
const mobileMenu = document.getElementById("mobile-menu");

if (toggleBtn && mobileMenu) {
    toggleBtn.addEventListener("click", () => {
    const isOpen = mobileMenu.classList.contains("max-h-0");

    if (isOpen) {
        mobileMenu.classList.remove("max-h-0", "opacity-0", "-translate-y-2");
        mobileMenu.classList.add("max-h-96", "opacity-100", "translate-y-0");
    } else {
        mobileMenu.classList.remove("max-h-96", "opacity-100", "translate-y-0");
        mobileMenu.classList.add("max-h-0", "opacity-0", "-translate-y-2");
    }
    });

}

// Profile dropdown
const profileToggle = document.getElementById("profile-toggle");
const profileMenu = document.getElementById("profile-menu");

if (profileToggle && profileMenu) {
    const openMenu = () => {
    profileMenu.classList.remove("hidden");
    profileToggle.setAttribute("aria-expanded", "true");
    };

    const closeMenu = () => {
    profileMenu.classList.add("hidden");
    profileToggle.setAttribute("aria-expanded", "false");
    };

    const isOpen = () => !profileMenu.classList.contains("hidden");

    profileToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    if (isOpen()) closeMenu();
    else openMenu();
    });

    // close menu after clicking on the outside
    document.addEventListener("click", (e) => {
    const clickedInside =
        profileMenu.contains(e.target) || profileToggle.contains(e.target);
    if (!clickedInside) closeMenu();
    });

    // close menu on ESC
    document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMenu();
    });

    // close menu after choosing an item
    profileMenu.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", closeMenu);
    });
}
});