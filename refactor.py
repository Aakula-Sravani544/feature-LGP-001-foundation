import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace the btn_generate UI and the rest of the extraction loop
start_marker = "            btn_generate = st.button("
end_marker = "def show_user_analytics(username: str) -> None:"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers")
    exit(1)

new_logic = """            btn_generate = False
            btn_resume = False
            
            # Show Resume if extraction stopped mid-way
            if not st.session_state.get("is_scraping", False) and st.session_state.get("remaining_leads", 0) > 0 and len(st.session_state.get("session_leads", [])) > 0:
                btn_resume = st.button(
                    f"▶️ Resume Extraction ({st.session_state.get('collected_leads', 0)}/{st.session_state.get('target_leads', 0)})",
                    key=f"btn_resume_{label_suffix}",
                    use_container_width=True
                )
            else:
                btn_generate = st.button(
                    "🚀 Generate Leads",
                    disabled=st.session_state.get("is_scraping", False),
                    key=f"btn_{label_suffix}",
                    use_container_width=True
                )

    if btn_generate:
        if max_leads > max_allowed:
            st.error(f"Your {current_plan} plan allows max {max_allowed} leads per session.")
            render_upgrade_banner(current_plan)
            return

        if source == "LinkedIn" and not can_use_linkedin(current_plan):
            st.error(get_upgrade_message(current_plan, "linkedin"))
            render_upgrade_banner(current_plan)
            st.stop()

        keyword = custom_keyword.strip() if custom_keyword.strip() else category
        if not city:
            st.warning("Please enter a city name.")
            return

        st.session_state.is_scraping = True
        st.session_state.target_leads = max_leads
        st.session_state.collected_leads = 0
        st.session_state.remaining_leads = max_leads
        st.session_state.session_leads = []
        st.session_state.logs = ""
        st.session_state.completed_batches = 0
        
        # State machine init
        st.session_state.keyword = keyword
        st.session_state.city = city
        st.session_state.region = region
        
        status_text = st.empty()
        status_text.text(f"🤖 AI analyzing sub-regions for {region or city}...")
        st.session_state.specific_sub_regions, st.session_state.fallback_areas = get_sub_regions_ai(keyword, region or city, city)
        
        st.session_state.phase = 1
        st.session_state.area_idx = 0
        st.session_state.fallback_idx = 0
        st.session_state.q_idx = 0
        st.session_state.consecutive_zero_yields = 0
        
        st.rerun()

    if btn_resume:
        st.session_state.is_scraping = True
        st.rerun()

    if st.session_state.get("is_scraping", False):
        progress_bar = st.progress(min(st.session_state.collected_leads / st.session_state.target_leads, 1.0) if st.session_state.target_leads else 0.0)
        status_text = st.empty()
        stop_placeholder = st.empty()
        log_placeholder = st.empty()
        metrics_placeholder = st.empty()
        table_placeholder = st.empty()

        with stop_placeholder.container():
            if st.button("⏹️ Stop Extraction", key=f"stop_{label_suffix}_{label_suffix}"):
                st.session_state.is_scraping = False
                st.warning("Extraction stopped by user. You can resume later.")
                import time as _time
                _time.sleep(2)
                st.rerun()

        with metrics_placeholder.container():
            m1, m2, m3 = st.columns(3)
            m1_metric = m1.empty()
            m2_metric = m2.empty()
            m3_metric = m3.empty()
            
        m1_metric.metric("Total Scraped", st.session_state.collected_leads)
        valid_count = len([x for x in st.session_state.session_leads if x.get("validation_status") == "Valid"])
        m2_metric.metric("Valid Leads", valid_count)
        
        try:
            df_db = database.load_db()
            db_leads_list = df_db.to_dict(orient="records")
        except:
            db_leads_list = []

        seen_session_ids = set()
        for l in st.session_state.session_leads:
            for k in get_lead_keys(l):
                seen_session_ids.add(k)

        # Batch execution
        batch_target = 25
        initial_collected = st.session_state.collected_leads
        batch_collected = 0
        duplicates_skipped = 0
        
        # UI log refresh
        log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
        
        while batch_collected < batch_target and st.session_state.collected_leads < st.session_state.target_leads:
            
            # Determine Query
            query = ""
            current_sub_region = ""
            
            if st.session_state.phase == 1:
                if st.session_state.area_idx >= len(st.session_state.specific_sub_regions):
                    st.session_state.phase = 2
                    st.session_state.logs += "[SYS] All sub-regions attempted. Starting broader fallback...\\n"
                    log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
                    continue
                    
                current_sub_region = st.session_state.specific_sub_regions[st.session_state.area_idx]
                query = f"{st.session_state.keyword} in {current_sub_region} {st.session_state.city}"
                st.session_state.logs += f"[SYS] Sub-region attempted: {current_sub_region} | Query: {query}\\n"
                
            elif st.session_state.phase == 2:
                if st.session_state.fallback_idx >= len(st.session_state.fallback_areas):
                    st.session_state.phase = 3
                    break
                    
                fallback_area = st.session_state.fallback_areas[st.session_state.fallback_idx]
                query_variants = get_query_variants(st.session_state.keyword)
                
                if st.session_state.q_idx >= len(query_variants):
                    st.session_state.fallback_idx += 1
                    st.session_state.q_idx = 0
                    st.session_state.consecutive_zero_yields = 0
                    continue
                    
                q_variant = query_variants[st.session_state.q_idx]
                if fallback_area:
                    query = f"{q_variant} in {fallback_area} {st.session_state.city}"
                else:
                    query = f"{q_variant} in {st.session_state.city}"
                st.session_state.logs += f"[SYS] Fallback Query: {query}\\n"
                current_sub_region = fallback_area
                
            else:
                break
                
            status_text.text(f"🔄 Scraping: {query} ({st.session_state.collected_leads}/{st.session_state.target_leads})")
            log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
            
            ai_flag = "1" if use_ai else "0"
            sub_batch_target = min(10, st.session_state.target_leads - st.session_state.collected_leads, batch_target - batch_collected)
            
            import subprocess
            import sys
            import json
            process = subprocess.Popen(
                [sys.executable, "scraper.py", query, str(sub_batch_target), ai_flag],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            leads_found_this_query = 0
            duplicates_skipped_this_query = 0
            unique_added_this_query = 0

            for line in process.stdout:
                line = line.strip()
                if line.startswith("DATA:"):
                    try:
                        data = json.loads(line.replace("DATA:", "").strip())
                        leads_found_this_query += 1

                        is_dup = False
                        data_keys = get_lead_keys(data)
                        for k in data_keys:
                            if k in seen_session_ids:
                                is_dup = True
                                break
                        
                        if not is_dup:
                            for db_lead in db_leads_list:
                                if is_db_duplicate_lead(data, db_lead):
                                    is_dup = True
                                    break

                        if not is_dup:
                            for k in data_keys:
                                seen_session_ids.add(k)
                                
                            st.session_state.session_leads.append(data)
                            database.save_to_db([data])
                            db_leads_list.append(data)
                            
                            unique_added_this_query += 1
                            st.session_state.collected_leads = len(st.session_state.session_leads)
                            st.session_state.remaining_leads = st.session_state.target_leads - st.session_state.collected_leads
                            batch_collected += 1
                        else:
                            duplicates_skipped_this_query += 1
                            duplicates_skipped += 1

                        valid_count = len([x for x in st.session_state.session_leads if x.get("validation_status") == "Valid"])
                        m1_metric.metric("Total Scraped", st.session_state.collected_leads)
                        m2_metric.metric("Valid Leads", valid_count)
                        m3_metric.metric("Duplicates Skipped", duplicates_skipped)
                        progress_bar.progress(min(st.session_state.collected_leads / st.session_state.target_leads, 1.0))

                        with table_placeholder.container():
                            import pandas as pd
                            df_view = pd.DataFrame(st.session_state.session_leads).iloc[::-1]
                            cols = [c for c in ["name", "phone", "email", "sub_region", "validation_status"] if c in df_view.columns]
                            st.dataframe(df_view[cols] if cols else df_view, hide_index=True)
                    except Exception as e:
                        import logging
                        logging.debug(f"Data parse error: {e}")

                elif line.startswith("LOG:"):
                    msg = line.replace("LOG:", "").strip()
                    st.session_state.logs += f"[SYS] {msg}\\n"
                    log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)

            process.wait()

            if st.session_state.phase == 1:
                if unique_added_this_query == 0:
                    st.session_state.logs += f"[SYS] Sub-region attempted: {current_sub_region} | Found 0 | Moving next\\n\\n"
                else:
                    st.session_state.logs += f"[SYS] Sub-region attempted: {current_sub_region} | Found {leads_found_this_query} | Unique added {unique_added_this_query}\\n\\n"
                st.session_state.area_idx += 1
                
            elif st.session_state.phase == 2:
                st.session_state.logs += f"[SYS] Found {leads_found_this_query} | Added {unique_added_this_query} | Total {st.session_state.collected_leads}/{st.session_state.target_leads}\\n\\n"
                if unique_added_this_query == 0:
                    st.session_state.consecutive_zero_yields += 1
                else:
                    st.session_state.consecutive_zero_yields = 0

                if st.session_state.consecutive_zero_yields >= 3:
                    st.session_state.logs += f"[SYS] Fallback area yielding no new leads. Moving to next fallback...\\n"
                    st.session_state.fallback_idx += 1
                    st.session_state.q_idx = 0
                    st.session_state.consecutive_zero_yields = 0
                else:
                    st.session_state.q_idx += 1
                    
            log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
            
        # End of batch
        if st.session_state.collected_leads >= st.session_state.target_leads or st.session_state.phase >= 3:
            st.session_state.is_scraping = False
            st.session_state.remaining_leads = 0
            if st.session_state.collected_leads >= st.session_state.target_leads:
                st.session_state.logs += f"[SYS] Target reached: {st.session_state.collected_leads}/{st.session_state.target_leads}\\n"
                st.success("✅ 100 leads generated successfully.")
            else:
                st.session_state.logs += f"[SYS] All fallback areas exhausted. Final total: {st.session_state.collected_leads}/{st.session_state.target_leads}\\n"
            
            log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
            status_text.text("✅ Extraction Complete! Syncing to Cloud...")
            success, msg = google_sheets.save_to_google_sheets(st.session_state.session_leads)
            import time as _time
            _time.sleep(2)
            st.rerun()
        else:
            # Batch limit hit, but target not reached. Re-run to process next batch automatically.
            st.session_state.completed_batches += 1
            st.rerun()

# ==========================================
# USER DASHBOARD
# ==========================================
"""

# Update the content
new_content = content[:start_idx] + new_logic + content[end_idx:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done replacing content in app.py")
