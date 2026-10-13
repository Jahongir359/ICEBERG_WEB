document.addEventListener('DOMContentLoaded', function () {
    const menu = document.querySelector('.public-menu');
    if (!menu) return;
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && menu.open) {
            menu.open = false;
            menu.querySelector('summary').focus();
        }
    });
    document.addEventListener('click', function (event) {
        if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
});
