// 导航栏功能
function initNavigation() {
    // 获取当前页面路径
    const currentPath = window.location.pathname;
    
    // 设置活动导航项
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (currentPath === href || (currentPath === '/' && href === '/dashboard')) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

// 页面加载时初始化导航
document.addEventListener('DOMContentLoaded', initNavigation);
