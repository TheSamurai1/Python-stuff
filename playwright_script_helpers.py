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
