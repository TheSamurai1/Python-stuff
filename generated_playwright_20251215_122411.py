import asyncio
import json
import os
import sys
from pathlib import Path
import urllib.parse
from playwright.async_api import async_playwright, Page, BrowserContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


# --- Helper Functions (from playwright_script_helpers.py) ---
"""
Helper functions for generated Playwright scripts.
This file contains utility functions used by the generated Playwright scripts.

Usage Examples:
    # Load sensitive data from JSON file
    from playwright_script_helpers import get_sensitive_data, replace_sensitive_data
    
    # Option 1: Load only from JSON file
    SENSITIVE_DATA = get_sensitive_data("sensitive_data.json")
    
    # Option 2: Load from JSON and merge with environment variables
    SENSITIVE_DATA = get_sensitive_data(
        "sensitive_data.json",
        env_vars={"username": "USERNAME", "password": "PASSWORD"}
    )
    
    # Use the data to replace placeholders
    text = "Hello {username}"
    result = replace_sensitive_data(text, SENSITIVE_DATA)
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class PlaywrightActionError(Exception):
    """Custom exception for Playwright action errors."""
    pass


def load_sensitive_data_from_json(json_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load sensitive data from a JSON file.
    
    This function handles paths passed from AGENT_RUNNER.py and resolves them correctly.
    For relative paths, it tries the current working directory first, then the script's directory.
    
    Args:
        json_path: Path to the JSON file. If None, defaults to 'sensitive_data.json'.
                   Supports both absolute and relative paths.
                   Relative paths are resolved from the current working directory.
                   Supports ~ for home directory expansion.
    
    Returns:
        Dictionary containing sensitive data from the JSON file.
        Returns empty dict if file doesn't exist or is invalid.
    
    Example:
        >>> data = load_sensitive_data_from_json("sensitive_data.json")
        >>> # or use default
        >>> data = load_sensitive_data_from_json()
        >>> # absolute path
        >>> data = load_sensitive_data_from_json("/path/to/variables.json")
        >>> # home directory
        >>> data = load_sensitive_data_from_json("~/config/variables.json")
        >>> # relative path (from AGENT_RUNNER.py)
        >>> data = load_sensitive_data_from_json("lol.json")
    """
    if json_path is None:
        json_path = "sensitive_data.json"
    
    # Expand user home directory if path starts with ~
    json_path = os.path.expanduser(json_path)
    original_path = json_path
    
    # Convert to Path object
    json_file = Path(json_path)
    
    # Try to resolve the path
    resolved_paths_to_try = []
    
    if json_file.is_absolute():
        # Absolute path - resolve it (handles symlinks, etc.)
        resolved_paths_to_try.append(json_file.resolve())
    else:
        # Relative path - try current working directory (most common case)
        # When helpers are embedded in generated scripts, relative paths work from cwd
        resolved_paths_to_try.append(Path.cwd() / json_file)
    
    # Try each resolved path until we find an existing file
    json_file = None
    for resolved_path in resolved_paths_to_try:
        if resolved_path.exists() and resolved_path.is_file():
            json_file = resolved_path
            break
    
    # If no file found, provide helpful error message
    if json_file is None:
        error_path = resolved_paths_to_try[0] if resolved_paths_to_try else Path(original_path)
        print(f"Warning: JSON file not found at {error_path} (original path: {original_path})", file=sys.stderr)
        print(f"  Current working directory: {Path.cwd()}", file=sys.stderr)
        if not Path(original_path).is_absolute():
            print(f"  Tip: Relative paths are resolved from the current working directory.", file=sys.stderr)
            print(f"  Tip: Use an absolute path or ensure the file exists in the current directory.", file=sys.stderr)
        return {}
    
    if not json_file.is_file():
        print(f"Warning: Path exists but is not a file: {json_file}, returning empty dict", file=sys.stderr)
        return {}
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                print(f"Warning: JSON file {json_file} does not contain a dictionary, returning empty dict", file=sys.stderr)
                return {}
            print(f"✅ Successfully loaded {len(data)} variable(s) from {json_file}", file=sys.stdout)
            return data
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {json_file}: {e}", file=sys.stderr)
        return {}
    except PermissionError as e:
        print(f"Error: Permission denied reading {json_file}: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error: Failed to load {json_file}: {e}", file=sys.stderr)
        return {}


def get_sensitive_data(json_path: Optional[str] = None, env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Get sensitive data by loading from JSON file and optionally merging with environment variables.
    
    This function loads data from a JSON file and can merge it with environment variables.
    Environment variables take precedence over JSON values if there's a conflict.
    
    Args:
        json_path: Path to the JSON file. If None, defaults to 'sensitive_data.json'.
        env_vars: Dictionary mapping keys to environment variable names. 
                  If provided, values will be loaded from environment variables.
                  Example: {"username": "USERNAME", "password": "PASSWORD"}
    
    Returns:
        Dictionary containing sensitive data, with env vars taking precedence.
    
    Example:
        >>> # Load only from JSON
        >>> data = get_sensitive_data("sensitive_data.json")
        >>> 
        >>> # Load from JSON and merge with env vars
        >>> data = get_sensitive_data(
        ...     "sensitive_data.json",
        ...     env_vars={"username": "USERNAME", "password": "PASSWORD"}
        ... )
    """
    # Load from JSON file
    sensitive_data = load_sensitive_data_from_json(json_path)
    
    # Merge with environment variables if provided
    if env_vars:
        for key, env_var_name in env_vars.items():
            env_value = os.getenv(env_var_name)
            if env_value:
                sensitive_data[key] = env_value
    
    return sensitive_data


def replace_sensitive_data(text: str, sensitive_data: dict) -> str:
    """Replace sensitive data placeholders with actual values."""
    if not text or not sensitive_data:
        return text
    result = text
    for key, value in sensitive_data.items():
        if isinstance(value, str):
            result = result.replace(f"{{{key}}}", value)
    return result


async def _try_locate_and_act(page, selector: str, action: str, text: str = None, step_info: str = ""):
    """Try to locate an element and perform an action with error handling."""
    try:
        # Wait for element to be visible and ready
        element = await page.wait_for_selector(selector, timeout=15000, state='visible')
        if not element:
            raise PlaywrightActionError(f"Element not found: {selector} ({step_info})")
        
        # Scroll element into view before interacting
        await element.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)  # Small delay to ensure element is ready
        
        if action == "click":
            await element.click()
            print(f"  Clicked element: {selector}")
        elif action == "fill":
            # Fill the element (fill() automatically clears the field first)
            await element.fill(text)
            print(f"  Filled element: {selector} with text: {text}")
        else:
            raise PlaywrightActionError(f"Unknown action: {action}")
    except Exception as e:
        # If the specific selector fails, try fallback strategies
        if action == "click":
            print(f"  Primary selector failed, trying fallback strategies...")
            try:
                # Check if we're on a different page (login successful)
                current_url = page.url
                if "login" not in current_url.lower():
                    print(f"  ✅ Login appears successful - redirected to: {current_url}")
                    
                    # Check if we're on an account selection page
                    try:
                        page_title = await page.title()
                        if "select" in page_title.lower() and "account" in page_title.lower():
                            print(f"  🔍 Detected account selection page: {page_title}")
                            # Try to click the first available account option
                            account_selectors = [
                                # Look for elements containing the email addresses
                                # "text=samarth.sridhara+dev12@tryjeeves.com",
                                # "text=samarth.sridhara@tryjeeves.com",
                                # Generic account selection selectors
                                "[data-testid*='account']",
                                ".account-card",
                                ".account-option", 
                                "[role='button']",
                                "button"
                            ]
                            
                            for account_selector in account_selectors:
                                try:
                                    print(f"    Trying account selector: {account_selector}")
                                    account_element = await page.wait_for_selector(account_selector, timeout=3000, state='visible')
                                    if account_element:
                                        await account_element.scroll_into_view_if_needed()
                                        await page.wait_for_timeout(300)
                                        await account_element.click()
                                        print(f"  ✅ Selected account using: {account_selector}")
                                        return
                                except:
                                    continue
                            
                            print(f"  ⚠️ Could not find account selection element, continuing...")
                            return
                    except:
                        pass
                    
                    print(f"  Skipping button click as we're no longer on login page")
                    return
                
                # Try common button selectors as fallback
                fallback_selectors = [
                    "button[type='submit']",
                    "input[type='submit']", 
                    "button:not([disabled])",
                    "[role='button']:not([disabled])",
                    "button",
                    "input[type='button']"
                ]
                
                for fallback_selector in fallback_selectors:
                    try:
                        print(f"    Trying fallback selector: {fallback_selector}")
                        fallback_element = await page.wait_for_selector(fallback_selector, timeout=3000, state='visible')
                        if fallback_element:
                            await fallback_element.scroll_into_view_if_needed()
                            await page.wait_for_timeout(300)
                            await fallback_element.click()
                            print(f"  ✅ Clicked fallback element: {fallback_selector}")
                            return
                    except Exception as fallback_error:
                        print(f"    Fallback selector {fallback_selector} failed: {fallback_error}")
                        continue
                        
                # If all fallbacks fail, raise the original error
                print(f"  ❌ All fallback strategies failed")
                raise e
            except:
                raise e
        else:
            # If the specific selector fails, try fallback strategies for input fields
            if action == "fill":
                print(f"  Primary selector failed, trying input fallback strategies...")
                try:
                    # Try common input selectors as fallback
                    input_fallbacks = [
                        "input[type='password']",
                        "input[type='text']",
                        "input:not([type])",
                        "input"
                    ]
                    
                    for fallback_selector in input_fallbacks:
                        try:
                            print(f"    Trying input fallback selector: {fallback_selector}")
                            fallback_element = await page.wait_for_selector(fallback_selector, timeout=3000, state='visible')
                            if fallback_element:
                                await fallback_element.scroll_into_view_if_needed()
                                await page.wait_for_timeout(300)
                                await fallback_element.fill(text)
                                print(f"  ✅ Filled fallback input element: {fallback_selector}")
                                return
                        except Exception as input_error:
                            print(f"    Input fallback selector {fallback_selector} failed: {input_error}")
                            continue
                            
                    # If all input fallbacks fail, raise the original error
                    print(f"  ❌ All input fallback strategies failed")
                    raise e
                except:
                    raise e
            else:
                error_msg = f"Failed to {action} element {selector} ({step_info}): {str(e)}"
                print(f"  Error: {error_msg}", file=sys.stderr)
                raise PlaywrightActionError(error_msg) from e

# --- End Helper Functions ---
# Sensitive data loaded from JSON file (credentials.json) with fallback to environment variables
# The helper functions (get_sensitive_data) are loaded above
# Default variables file path and env vars mapping (can be overridden with --variables)
_DEFAULT_VARIABLES_PATH = "credentials.json"
_ENV_VARS_MAPPING = {
    "username": "USERNAME",
    "password": "PASSWORD",
    "website": "WEBSITE"
}
# SENSITIVE_DATA will be initialized after parsing command-line arguments in __main__ block
# Initialize as empty dict at module level (will be populated in __main__)
SENSITIVE_DATA = {}

async def run_generated_script():
    global SENSITIVE_DATA
    async with async_playwright() as p:
        browser = None
        context = None
        page = None
        exit_code = 0 # Default success exit code
        try:
            print('Launching chromium browser...')
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            print('Browser context created.')
            # Initial page handling
            if context.pages:
                page = context.pages[0]
                print('Using initial page provided by context.')
            else:
                page = await context.new_page()
                print('Created a new page as none existed.')
            print('\n--- Starting Generated Script Execution ---')
            # Navigate to initial URL
            print(f"Navigating to: https://develop-08.dev.tryjeeves.com/client/web/login")
            await page.goto("https://develop-08.dev.tryjeeves.com/client/web/login", timeout=90000, wait_until="domcontentloaded")
            # Function to check if login was successful
            def check_login_success():
                current_url = page.url
                return "login" not in current_url.lower()

            # Function to handle account selection (generic for Jeeves workflows)
            async def handle_account_selection():
                try:
                    page_title = await page.title()
                    if "select" in page_title.lower() and "account" in page_title.lower():
                        print(f"  🔍 Detected account selection page: {page_title}")
                        # Try to select the first available account
                        account_selectors = [
                            # Generic account selectors - no hardcoded email addresses
                            "[data-testid*='account']",
                            ".account-card",
                            "[data-testid*='select']",
                            # ".account-option",
                            # "[role='button']",
                            # "button"
                        ]
                        
                        for selector in account_selectors:
                            try:
                                print(f"    Trying account selector: {selector}")
                                element = await page.wait_for_selector(selector, timeout=3000, state="visible")
                                if element:
                                    await element.scroll_into_view_if_needed()
                                    # Removed unnecessary wait_for_timeout(300) - no longer needed
                                    await element.click()
                                    print(f"  ✅ Selected account using: {selector}")
                                    return True
                            except:
                                continue
                        
                        print(f"  ⚠️ Could not find account selection element")
                        return False
                except:
                    return False


            # --- Step 1 ---
            # Action 1
            print(f"Waiting for 5 seconds... (Step 1, Action 1)")
            await asyncio.sleep(5)
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 2 ---
            # Action 2
            await _try_locate_and_act(page, "xpath=//html/body/div/div[3]/form/div[2]/div/input", "fill", text=replace_sensitive_data("{username}", SENSITIVE_DATA), step_info="Step 2, Action 1")
            # Check if we need to handle account selection
            await handle_account_selection()
            # Action 3
            # Attempting click_element_by_index with generic selector (Step 2, Action 2)
            try:
                # Try common clickable selectors in order of preference
                click_selectors = [
                    "button[type=\"submit\"]",
                    "input[type=\"submit\"]",
                    "button:not([disabled])",
                    "[data-testid*=\"button\"]",
                    "[aria-label*=\"button\"]",
                    "button[data-testid]",
                    "button[aria-label]",
                    "[data-testid*=\"delete\"]",
                    "[data-testid*=\"trash\"]",
                    "[aria-label*=\"delete\"]",
                    "[aria-label*=\"trash\"]",
                    "button:has(svg[data-testid*=\"delete\"])",
                    "button:has(svg[data-testid*=\"trash\"])",
                    "button:has(svg[aria-label*=\"delete\"])",
                    "button:has(svg[aria-label*=\"trash\"])",
                ]
                for selector in click_selectors:
                    try:
                        print(f"    Trying fallback selector: {selector}")
                        await _try_locate_and_act(page, selector, "click", step_info="Step 2, Action 2")
                        print(f"  ✅ Successfully clicked with selector: {selector}")
                        break
                    except Exception as fallback_error:
                        print(f"    Fallback selector {selector} failed: {fallback_error}")
                        continue
            except Exception as e:
                print(f"  ❌ All fallback strategies failed for (Step 2, Action 2): {e}", file=sys.stderr)
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 3 ---
            # Action 4
            await _try_locate_and_act(page, "xpath=//html/body/div/div[3]/form/div[3]/button", "click", step_info="Step 3, Action 1")
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 4 ---
            # Action 5
            print(f"Waiting for 5 seconds... (Step 4, Action 1)")
            await asyncio.sleep(5)
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 5 ---
            # Action 6
            await _try_locate_and_act(page, "xpath=//html/body/div/div[3]/form/div[3]/div/input", "fill", text=replace_sensitive_data("{password}", SENSITIVE_DATA), step_info="Step 5, Action 1")
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 6 ---
            # Action 7
            await _try_locate_and_act(page, "xpath=//html/body/div/div[3]/form/div[5]/button[2]", "click", step_info="Step 6, Action 1")
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 7 ---
            # Action 8
            await _try_locate_and_act(page, "xpath=//html/body/div/div[3]/div[2]/div/div[1]/div/div[2]", "click", step_info="Step 7, Action 1")
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 8 ---
            # Action 9
            print(f"Waiting for 5 seconds... (Step 8, Action 1)")
            await asyncio.sleep(5)
            # Check if we need to handle account selection
            await handle_account_selection()

            # --- Step 9 ---
            # Action 10
            print("\n--- Task marked as Done by agent (Step 9, Action 1) ---")
            print(f"Agent reported success: True")
            # Final Message from agent (may contain placeholders):
            final_message = replace_sensitive_data("Successfully logged into the website using the provided username and password.", SENSITIVE_DATA)
            print(final_message)
            # Check if we need to handle account selection
            await handle_account_selection()
        except PlaywrightActionError as pae:
            print(f'\n--- Playwright Action Error: {pae} ---', file=sys.stderr)
            exit_code = 1
        except Exception as e:
            print(f'\n--- An unexpected error occurred: {e} ---', file=sys.stderr)
            import traceback
            traceback.print_exc()
            exit_code = 1
        finally:
            print('\n--- Generated Script Execution Finished ---')
            print('Closing browser/context...')
            if context:
                 try: await context.close()
                 except Exception as ctx_close_err: print(f'  Warning: could not close context: {ctx_close_err}', file=sys.stderr)
            if browser:
                 try: await browser.close()
                 except Exception as browser_close_err: print(f'  Warning: could not close browser: {browser_close_err}', file=sys.stderr)
            print('Browser/context closed.')
            # Exit with the determined exit code
            if exit_code != 0:
                print(f'Script finished with errors (exit code {exit_code}).', file=sys.stderr)
                sys.exit(exit_code)

# --- Script Entry Point ---
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Run generated Playwright script")
    parser.add_argument("--variables", "-v", dest="variables_file",
                        default=_DEFAULT_VARIABLES_PATH,
                        help=f"Path to JSON file containing sensitive data variables (default: {{_DEFAULT_VARIABLES_PATH}})")
    args = parser.parse_args()
    
    # Normalize paths for comparison (expand user dir and resolve if exists)
    def normalize_path(p):
        expanded = os.path.expanduser(p)
        path_obj = Path(expanded)
        if path_obj.exists():
            return str(path_obj.resolve())
        # If path doesn't exist, return normalized absolute path
        if path_obj.is_absolute():
            return str(path_obj)
        return str(Path.cwd() / path_obj)
    
    default_path_normalized = normalize_path(_DEFAULT_VARIABLES_PATH)
    provided_path_normalized = normalize_path(args.variables_file)
    
    # Load SENSITIVE_DATA from the specified file (default or overridden)
    variables_file_to_use = args.variables_file
    
    if provided_path_normalized != default_path_normalized:
        print(f"Loading variables from: {variables_file_to_use}")
    else:
        print(f"Loading variables from default file: {_DEFAULT_VARIABLES_PATH}")
    
    # Load the variables file
    if _ENV_VARS_MAPPING:
        SENSITIVE_DATA = get_sensitive_data(variables_file_to_use, env_vars=_ENV_VARS_MAPPING)
    else:
        SENSITIVE_DATA = get_sensitive_data(variables_file_to_use)
    
    # Verify that data was loaded
    if not SENSITIVE_DATA:
        print(f"Warning: No variables loaded from {variables_file_to_use}. Check if file exists and contains valid JSON.", file=sys.stderr)
    else:
        print(f"✅ Loaded {len(SENSITIVE_DATA)} variable(s): {list(SENSITIVE_DATA.keys())}")
    
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_generated_script())