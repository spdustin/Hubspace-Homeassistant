#!/usr/bin/env python3
"""Test script for night-light switch functionality."""

from tests.utils import create_devices_from_data


def test_night_light_detection():
    """Test that night-light capability is detected correctly."""
    
    # Load exhaust fan devices
    devices = create_devices_from_data('fan-exhaust-fan.json')
    
    # Find the light device
    light_device = None
    for device in devices:
        if device.device_class == 'light':
            light_device = device
            break
    
    assert light_device is not None, "No light device found in exhaust fan data"
    
    print(f"Testing light device: {light_device.id} ({light_device.friendly_name})")
    
    # Test night-light capability detection
    has_night_light = False
    for func in light_device.functions:
        if func.get("functionClass") == "color-mode":
            print(f"Found color-mode function with {len(func.get('values', []))} values:")
            for value in func.get("values", []):
                print(f"  - {value.get('name')} (hints: {value.get('hints', [])})")
                if value.get("name") == "night-light":
                    has_night_light = True
    
    print(f"Has night-light capability: {has_night_light}")
    assert has_night_light, "Light should have night-light capability"
    
    # Test current state
    current_color_mode = None
    for state in light_device.states:
        if state.functionClass == "color-mode":
            current_color_mode = state.value
            break
    
    print(f"Current color mode: {current_color_mode}")
    
    # Test night-light switch logic
    is_night_light_on = current_color_mode == "night-light"
    print(f"Night-light currently on: {is_night_light_on}")
    
    print("\nNight-light detection test passed!")
    return True


if __name__ == "__main__":
    test_night_light_detection()