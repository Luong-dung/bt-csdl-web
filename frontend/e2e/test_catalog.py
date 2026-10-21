from playwright.sync_api import Page, expect

from helpers import login, unique_username


def catalog_group(page: Page, heading: str):
    return page.locator(".catalog-lists > div").filter(
        has=page.get_by_role("heading", name=heading, exact=True)
    )


def test_admin_can_manage_catalog_and_viewer_cannot(page: Page, demo_password: str):
    page.get_by_label("Tên đăng nhập").fill("demo_viewer")
    page.get_by_label("Mật khẩu").fill(demo_password)
    page.get_by_role("button", name="Đăng nhập").click()
    expect(page.get_by_role("heading", name="Tài khoản đã xác thực")).to_be_visible()
    expect(page.get_by_role("button", name="Thêm publisher")).to_have_count(0)
    expect(page.locator(".catalog-panel")).to_contain_text(
        "Chỉ ADMIN được thêm, sửa hoặc xóa"
    )

    page.get_by_role("button", name="Đăng xuất").click()
    login(page, "demo_admin", demo_password)

    suffix = unique_username("catalog")[-8:]
    publisher = f"Playwright Publisher {suffix}"
    renamed_publisher = f"Playwright Publisher Updated {suffix}"
    game = f"Playwright Game {suffix}"
    slug = f"playwright-game-{suffix}"
    updated_game = f"Playwright Game Updated {suffix}"
    updated_slug = f"playwright-game-updated-{suffix}"
    area = f"Playwright Area {suffix}"
    area_code = f"PW-{suffix.upper()}"
    updated_area = f"Playwright Area Updated {suffix}"
    updated_area_code = f"PWU-{suffix.upper()}"

    page.get_by_label("Tên publisher").fill(publisher)
    page.get_by_role("button", name="Thêm publisher").click()
    expect(catalog_group(page, "Publishers")).to_contain_text(publisher)

    publisher_item = catalog_group(page, "Publishers").locator(
        ".catalog-item"
    ).filter(has_text=publisher)
    page.once("dialog", lambda dialog: dialog.accept(renamed_publisher))
    publisher_item.get_by_role("button", name="Sửa").click()
    expect(catalog_group(page, "Publishers")).to_contain_text(renamed_publisher)

    publisher_option = page.locator('select[name="publisher_id"]')
    publisher_option.select_option(label=renamed_publisher)
    publisher_id = publisher_option.input_value()
    page.get_by_label("Tên game").fill(game)
    page.get_by_label("Slug").fill(slug)
    page.get_by_role("button", name="Thêm game").click()
    expect(catalog_group(page, "Games")).to_contain_text(game)

    game_item = catalog_group(page, "Games").locator(".catalog-item").filter(
        has_text=slug
    )
    dialog_values = iter((updated_game, updated_slug, publisher_id))
    dialog_handler = lambda dialog: dialog.accept(next(dialog_values))
    page.on("dialog", dialog_handler)
    try:
        game_item.get_by_role("button", name="Sửa").click()
    finally:
        page.remove_listener("dialog", dialog_handler)
    expect(catalog_group(page, "Games")).to_contain_text(updated_slug)

    page.get_by_label("Tên khu vực").fill(area)
    page.get_by_label("Mã", exact=True).fill(area_code)
    page.get_by_label("Khu vực cha").select_option(label="VN · Vietnam")
    parent_id = page.get_by_label("Khu vực cha").input_value()
    page.get_by_role("button", name="Thêm khu vực").click()
    expect(catalog_group(page, "Khu vực")).to_contain_text(area_code)

    area_item = catalog_group(page, "Khu vực").locator(".catalog-item").filter(
        has_text=area_code
    )
    area_dialog_values = iter((updated_area, updated_area_code, parent_id))
    area_dialog_handler = lambda dialog: dialog.accept(next(area_dialog_values))
    page.on("dialog", area_dialog_handler)
    try:
        area_item.get_by_role("button", name="Sửa").click()
    finally:
        page.remove_listener("dialog", area_dialog_handler)
    expect(catalog_group(page, "Khu vực")).to_contain_text(updated_area_code)

    publisher_item = catalog_group(page, "Publishers").locator(
        ".catalog-item"
    ).filter(has_text=renamed_publisher)
    page.once("dialog", lambda dialog: dialog.accept())
    publisher_item.get_by_role("button", name="Xóa").click()
    expect(page.locator(".message.error")).to_contain_text(
        "Nhà phát hành vẫn còn game"
    )

    game_item = catalog_group(page, "Games").locator(".catalog-item").filter(
        has_text=updated_slug
    )
    page.once("dialog", lambda dialog: dialog.accept())
    game_item.get_by_role("button", name="Xóa").click()
    expect(catalog_group(page, "Games")).not_to_contain_text(updated_slug)

    publisher_item = catalog_group(page, "Publishers").locator(
        ".catalog-item"
    ).filter(has_text=renamed_publisher)
    page.once("dialog", lambda dialog: dialog.accept())
    publisher_item.get_by_role("button", name="Xóa").click()
    expect(catalog_group(page, "Publishers")).not_to_contain_text(renamed_publisher)

    area_item = catalog_group(page, "Khu vực").locator(".catalog-item").filter(
        has_text=updated_area_code
    )
    page.once("dialog", lambda dialog: dialog.accept())
    area_item.get_by_role("button", name="Xóa").click()
    expect(catalog_group(page, "Khu vực")).not_to_contain_text(updated_area_code)
