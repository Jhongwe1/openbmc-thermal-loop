*** Settings ***
Documentation    Verify the modern ThermalSubsystem and Sensors resources
...              under each chassis (Chassis schema v1.15+). The suite is
...              QEMU-safe by design: a stock QEMU image exposes an empty
...              Sensors collection, so membership is validated structurally
...              instead of against a fixed sensor list.
...
...              DRAFT for openbmc-test-automation (candidate patch A,
...              see docs/upstream.md). Intended location:
...              redfish/systems/test_thermal_subsystem.robot, with both
...              tags added to test_lists/QEMU_CI. To try it, copy the file
...              into the clone so the ../../lib resource paths resolve.

Resource         ../../lib/bmc_redfish_resource.robot
Resource         ../../lib/bmc_redfish_utils.robot

Suite Setup      Redfish.Login
Suite Teardown   Redfish.Logout

Test Tags        Thermal_Subsystem


*** Test Cases ***

Verify Chassis Thermal Subsystem Resources
    [Documentation]  Every chassis that advertises a ThermalSubsystem must
    ...              serve it with a valid resource type.
    [Tags]  Verify_Chassis_Thermal_Subsystem_Resources

    ${chassis_uris}=  Redfish_Utils.Get Member List  /redfish/v1/Chassis
    Should Not Be Empty  ${chassis_uris}

    VAR  ${subsystems_checked}  ${0}

    FOR  ${chassis_uri}  IN  @{chassis_uris}
        ${chassis}=  Redfish.Get Properties  ${chassis_uri}
        ${advertised}=  Evaluate  'ThermalSubsystem' in $chassis
        IF  not ${advertised}  CONTINUE

        ${resp}=  Redfish.Get  ${chassis['ThermalSubsystem']['@odata.id']}
        ...  valid_status_codes=[${HTTP_OK}]
        Should Start With  ${resp.dict['@odata.type']}  \#ThermalSubsystem
        ${subsystems_checked}=  Evaluate  ${subsystems_checked} + 1
    END

    Log  Validated ${subsystems_checked} ThermalSubsystem resource(s).


Verify Chassis Sensors Collection
    [Documentation]  Every chassis Sensors collection must respond, report a
    ...              member count consistent with its member list, and every
    ...              member must serve a non-null Reading. An empty
    ...              collection is valid: a stock QEMU image exposes no
    ...              sensors, so this case must not assert on sensor names.
    [Tags]  Verify_Chassis_Sensors_Collection

    ${chassis_uris}=  Redfish_Utils.Get Member List  /redfish/v1/Chassis
    Should Not Be Empty  ${chassis_uris}

    VAR  ${sensors_checked}  ${0}

    FOR  ${chassis_uri}  IN  @{chassis_uris}
        ${chassis}=  Redfish.Get Properties  ${chassis_uri}
        ${advertised}=  Evaluate  'Sensors' in $chassis
        IF  not ${advertised}  CONTINUE

        ${resp}=  Redfish.Get  ${chassis['Sensors']['@odata.id']}
        ...  valid_status_codes=[${HTTP_OK}]

        ${members}=  Set Variable  ${resp.dict['Members']}
        ${count}=  Get Length  ${members}
        Should Be Equal As Integers  ${count}
        ...  ${resp.dict['Members@odata.count']}

        FOR  ${member}  IN  @{members}
            ${sensor}=  Redfish.Get Properties  ${member['@odata.id']}
            Should Not Be Equal  ${sensor['Reading']}  ${null}
            ...  msg=${member['@odata.id']} serves a null Reading.
            ${sensors_checked}=  Evaluate  ${sensors_checked} + 1
        END
    END

    Log  Validated ${sensors_checked} sensor member(s); an empty set is
    ...  acceptable on stock QEMU images.
