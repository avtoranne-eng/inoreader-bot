def main():
    if not TG_TOKEN or not TG_CHAT_ID:
        print("Отсутствуют ключи Telegram!", flush=True)
        return

    processed = get_processed()
    count = 0

    for category in CATEGORY_URLS:
        if count >= MAX_MODS_PER_RUN:
            print("🎉 Достигнут лимит скачиваний на этот запуск. Иду отдыхать!")
            break

        current_page_url = category
        print(f"--- Раздел: {category} ---", flush=True)
        
        category_done = False # Флаг умной остановки для текущей категории

        for page in range(1, MAX_PAGES + 1):
            if count >= MAX_MODS_PER_RUN or category_done:
                break

            try:
                resp = requests.get(current_page_url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                mod_links = []

                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    full_url = urljoin(current_page_url, href)

                    if not full_url.startswith("https://sims4pack.ru/"):
                        continue

                    if any(bad in full_url.lower() for bad in BLACKLIST):
                        continue

                    if '/mods/' not in full_url.lower() and not re.search(r'/\d+-', full_url):
                        continue

                    if full_url not in mod_links:
                        mod_links.append(full_url)

                # --- УМНЫЙ ПОИСК СЛЕДУЮЩЕЙ СТРАНИЦЫ ---
                next_page_url = None
                for a in soup.find_all('a', href=True):
                    text = a.text.strip()
                    if text == str(page + 1): 
                        next_page_url = urljoin(resp.url, a.get('href'))
                        break

                if not next_page_url:
                    for a in soup.find_all('a', href=True):
                        text = a.text.strip().lower()
                        if 'вперед' in text or 'далее' in text or '»' in text:
                            next_page_url = urljoin(resp.url, a.get('href'))
                            break
                # --------------------------------------

                if mod_links:
                    for link in mod_links:
                        if count >= MAX_MODS_PER_RUN:
                            break
                        
                        # ВОТ ОНА - УМНАЯ ОСТАНОВКА!
                        if link in processed:
                            print(f"🛑 Знакомый мод: {link}. В этой категории свежего больше нет, идем дальше!")
                            category_done = True # Поднимаем флаг
                            break # Выходим из цикла ссылок

                        print(f"Скачиваю [Стр. {page}]: {link}", flush=True)

                        try:
                            mod_resp = requests.get(link, headers=HEADERS, timeout=15)
                            if mod_resp.status_code != 200:
                                continue

                            mod_soup = BeautifulSoup(mod_resp.text, 'html.parser')

                            title_tag = mod_soup.find('h1')
                            title = title_tag.text.strip() if title_tag else "Мод для The Sims 4"

                            img_url = extract_image(mod_soup)
                            if img_url:
                                img_url = urljoin(link, img_url)

                            download_link = None
                            for a in mod_soup.find_all('a', href=True):
                                href_a = a.get('href', '')
                                text_a = a.text.strip().lower()
                                classes_a = " ".join(a.get('class', [])).lower()

                                full_dl = urljoin(link, href_a)

                                if full_dl.rstrip('/').endswith('/downloads'):
                                    continue

                                if 'download' in classes_a or 'download' in href_a.lower() or 'скачать' in text_a:
                                    download_link = full_dl
                                    break

                            if download_link:
                                file_resp = requests.get(download_link, headers=HEADERS, stream=True, timeout=30)
                                if file_resp.status_code == 200:

                                    content_type = file_resp.headers.get('Content-Type', '').lower()
                                    if 'text/html' in content_type:
                                        continue

                                    filename = "mod.package"
                                    if "Content-Disposition" in file_resp.headers:
                                        cd = file_resp.headers["Content-Disposition"]
                                        if "filename=" in cd:
                                            filename = cd.split("filename=")[-1].strip('"').strip("'")

                                    with open(filename, 'wb') as f:
                                        for chunk in file_resp.iter_content(chunk_size=8192):
                                            f.write(chunk)

                                    send_to_telegram(title, img_url, filename)
                                    mark_processed(link)
                                    processed.append(link)

                                    count += 1
                                    time.sleep(5)

                        except Exception as e:
                            print(f"Ошибка при обработке {link}: {e}", flush=True)

                if not next_page_url or category_done:
                    break

                current_page_url = next_page_url

            except Exception as e:
                print(f"Ошибка раздела {current_page_url}: {e}", flush=True)
                break
